"""
Streamlit Frontend UI for Adaptive Learning Coach.
Stored inside ui/ to keep presentation code modular, clean, and decoupled.

Displays the complete intelligent tutoring experience strictly from an end-user perspective:
- Learner Profile & Quiz Simulator
- Real-Time Pedagogical Performance Signals (EWMA Mastery, Trend Analysis, Gap Detection)
- Empathetic AI Coaching Feedback & Guardrailed Pedagogical Advice
- Curricular Progression & Database Persistence
"""

import os
import sqlite3
import streamlit as st
from dotenv import load_dotenv

# Load environment variables (e.g. GEMINI_API_KEY)
load_dotenv()

from ai.learning_intelligence import (
    LearnerContext,
    DifficultyLevel,
    DecisionType,
    compute_performance_metrics,
    create_learning_assessment,
    evaluate_and_decide,
    evaluate_deterministic,
)
from ai.prompts import build_user_prompt
from validation import (
    clean_quiz_submission,
    validate_student_exists,
    validate_attempt_record,
    build_validated_learner_context,
)
from actions import (
    apply_learning_decision,
    record_quiz_attempt,
    get_student,
    LEARNING_LEVELS,
)
from database.seed import seed_database

# Optional Gemini agent connection
try:
    from ai.agent import get_learning_decision as call_gemini_agent
    GEMINI_AGENT_AVAILABLE = True
except ImportError:
    call_gemini_agent = None
    GEMINI_AGENT_AVAILABLE = False

DB_PATH = os.path.join(os.path.dirname(__file__), "../data/learning_coach.db")


def load_students_from_db():
    """Queries active student profiles from SQLite."""
    if not os.path.exists(DB_PATH):
        return []
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT student_id, name, current_level FROM students ORDER BY student_id ASC")
    students = cursor.fetchall()
    conn.close()
    return students


def load_student_attempts(student_id: str):
    """Queries quiz attempt history for a student from SQLite."""
    if not os.path.exists(DB_PATH):
        return []
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT topic, difficulty, score, time_spent_seconds, timestamp
        FROM quiz_attempts
        WHERE student_id = ?
        ORDER BY attempt_id ASC
    """, (student_id,))
    attempts = cursor.fetchall()
    conn.close()
    return attempts


def run_dashboard():
    """Main Streamlit Dashboard renderer."""
    st.set_page_config(
        page_title="Adaptive Learning Coach — Intelligent Tutoring Platform",
        page_icon="🧠",
        layout="wide",
        initial_sidebar_state="expanded",
    )

    # -------------------------------------------------------------
    # 1. HEADER & APPLICATION BRANDING
    # -------------------------------------------------------------
    st.title("🧠 Adaptive Learning Coach")
    st.caption("Real-Time Personalized Learning Intelligence & Pedagogical Guidance Platform")

    st.markdown("---")

    # -------------------------------------------------------------
    # 2. SIDEBAR: LEARNER SELECTOR & QUIZ SIMULATOR
    # -------------------------------------------------------------
    st.sidebar.header("👤 Learner Profile")

    # Quick seed/reset button for testing different scenarios
    if st.sidebar.button("🔄 Reset to Default Learners", help="Restores database to baseline learner states"):
        seed_database()
        st.sidebar.success("Learner profiles reset to baseline!")
        st.rerun()

    students = load_students_from_db()
    if not students:
        st.sidebar.error("⚠️ Database is empty. Please click 'Reset to Default Learners' to initialize.")
        return

    student_options = {f"{s[1]} (ID: {s[0]} • {s[2]})": s for s in students}
    selected_label = st.sidebar.selectbox("Active Learner:", list(student_options.keys()))
    selected_student = student_options[selected_label]
    student_id, student_name, student_level = selected_student

    # Load attempts
    attempts = load_student_attempts(student_id)
    if not attempts:
        st.sidebar.warning(f"No quiz history found for {student_name}.")
        return

    # Extract distinct topics
    topics = list(dict.fromkeys([a[0] for a in attempts]))
    selected_topic = st.sidebar.selectbox("Module Topic:", topics)

    # Filter attempts for this topic
    topic_attempts = [a for a in attempts if a[0] == selected_topic]
    past_scores = [float(a[2]) for a in topic_attempts[:-1]]
    latest_attempt = topic_attempts[-1]
    latest_score = float(latest_attempt[2])
    latest_diff = latest_attempt[1]
    latest_time = latest_attempt[3] or 60

    st.sidebar.markdown("---")
    st.sidebar.subheader("📝 Practice Quiz Simulation")
    sim_score = st.sidebar.slider("Quiz Score (%):", 0.0, 100.0, latest_score, 1.0)
    sim_time = st.sidebar.number_input("Time Spent (seconds):", 10, 600, latest_time, 5)
    sim_difficulty = st.sidebar.selectbox(
        "Exercise Difficulty:",
        LEARNING_LEVELS,
        index=LEARNING_LEVELS.index(latest_diff.upper()) if latest_diff.upper() in LEARNING_LEVELS else 0
    )

    use_gemini = st.sidebar.checkbox(
        "Enable Real-Time Generative Feedback",
        value=bool(os.getenv("GEMINI_API_KEY")),
        help="Connects to Gemini for personalized empathetic feedback, with guaranteed pedagogical guardrails."
    )

    # -------------------------------------------------------------
    # 3. TOP LEARNER STATS BAR
    # -------------------------------------------------------------
    learner_data = get_student(student_id, db_path=DB_PATH)
    active_level = learner_data["current_level"] if learner_data else student_level

    stat_col1, stat_col2, stat_col3, stat_col4 = st.columns(4)
    with stat_col1:
        st.metric("Learner", student_name, f"ID: {student_id}")
    with stat_col2:
        st.metric("Curriculum Level", active_level)
    with stat_col3:
        st.metric("Current Module", selected_topic)
    with stat_col4:
        st.metric("Total Attempts", len(topic_attempts))

    st.markdown("---")

    # -------------------------------------------------------------
    # 4. SUBMISSION VERIFICATION & CONTEXT
    # -------------------------------------------------------------
    # Validate submission
    validation_passed = True
    val_error = None
    try:
        cleaned_sub = clean_quiz_submission(
            student_id=student_id,
            topic=selected_topic,
            difficulty=sim_difficulty,
            raw_score=sim_score,
            time_spent=sim_time,
        )
    except Exception as e:
        validation_passed = False
        val_error = str(e)

    if not validation_passed:
        st.error(f"❌ Input Validation Error: {val_error}")
        return

    # Build validated context
    context = build_validated_learner_context(
        student_id=student_id,
        topic=selected_topic,
        raw_score=sim_score,
        time_spent=sim_time,
        difficulty=sim_difficulty,
        db_path=DB_PATH,
    )

    # -------------------------------------------------------------
    # 5. RUN INTELLIGENCE ENGINE & AI EVALUATION
    # -------------------------------------------------------------
    metrics = compute_performance_metrics(context)
    assessment = create_learning_assessment(context)

    # Gemini agent connector
    agent_caller = None
    if use_gemini and GEMINI_AGENT_AVAILABLE and os.getenv("GEMINI_API_KEY"):
        def agent_bridge(prompt_ctx):
            learner_dict, metrics_dict = assessment.to_member1_format(time_spent_seconds=sim_time)
            return call_gemini_agent(learner_dict, metrics_dict)
        agent_caller = agent_bridge

    # Evaluate decision with safety guardrail
    final_decision = evaluate_and_decide(context, ai_agent_caller=agent_caller)

    # -------------------------------------------------------------
    # 6. MAIN DISPLAY: PERFORMANCE SIGNALS & COACHING ADVICE
    # -------------------------------------------------------------
    col_intel, col_ai = st.columns([1.1, 1.2])

    # Left Column: Quantitative Pedagogical Signals
    with col_intel:
        st.subheader("📊 Performance Analytics")

        m_col1, m_col2 = st.columns(2)
        with m_col1:
            st.metric("Mastery Index (EWMA)", f"{metrics.mastery_score}%")
        with m_col2:
            trend_icon = "📈" if metrics.score_trend.value == "IMPROVING" else ("📉" if metrics.score_trend.value == "DECLINING" else "➡️")
            st.metric("Trajectory Trend", f"{trend_icon} {metrics.score_trend.value.title()}")

        m_col3, m_col4 = st.columns(2)
        with m_col3:
            fail_color = "red" if metrics.consecutive_failures >= 3 else "normal"
            st.metric("Consecutive Struggles", f"{metrics.consecutive_failures} / 3")
        with m_col4:
            st.metric("Historical Average", f"{metrics.historical_average}%")

        # Pedagogical Diagnostic Badges
        st.markdown("**Pedagogical Diagnostics:**")
        badge_html = " ".join([
            f"<span style='background-color:#1e3a8a;color:#93c5fd;padding:4px 10px;border-radius:12px;font-size:12px;margin-right:5px;'>🏷️ {code.value.replace('_', ' ').title()}</span>"
            for code in assessment.reason_codes
        ])
        st.markdown(badge_html, unsafe_allow_html=True)

        st.markdown("**Historical Score Trajectory:**")
        st.line_chart(context.full_score_sequence())

    # Right Column: AI Coaching & Guidance
    with col_ai:
        st.subheader("💬 AI Coach Guidance")
        st.success("🛡️ **Safety Guardrail:** Verified against pedagogical bounds")

        # Coach Message Card
        st.info(f"💡 **Coach Advice:**\n\n\"{final_decision.coaching_narrative}\"")

        # Strategy Card
        with st.expander("⚙️ Pedagogical Assessment Details", expanded=True):
            s1, s2 = st.columns(2)
            with s1:
                st.write(f"**Recommended Action:** `{final_decision.decision.value}`")
                st.write(f"**Target Strategy:** `{final_decision.strategy.value.replace('_', ' ').title()}`")
            with s2:
                st.write(f"**Coach Confidence:** `{final_decision.confidence * 100:.0f}%`")
                st.write(f"**Target Difficulty:** `{final_decision.target_difficulty.value}`")

        with st.expander("🔍 Detailed Submission & Context Inspection", expanded=False):
            st.write("**Validated Quiz Submission:**")
            st.json(cleaned_sub)
            st.write(f"**Prior Score History ({len(context.score_history)} attempts):**", context.score_history)

    # -------------------------------------------------------------
    # 7. CURRICULAR PROGRESSION & ACTION COMMIT
    # -------------------------------------------------------------
    st.markdown("---")
    st.subheader("🎯 Curricular Progression & Pathway Update")

    col_act1, col_act2 = st.columns([1, 1.3])

    with col_act1:
        color_map = {
            DecisionType.ADVANCE: "#10b981",   # Emerald green
            DecisionType.MENTOR: "#f59e0b",    # Amber orange
            DecisionType.REINFORCE: "#ef4444", # Coral red
        }
        dec_color = color_map.get(final_decision.decision, "#3b82f6")
        
        decision_label_map = {
            DecisionType.ADVANCE: "ADVANCE TO NEXT LEVEL",
            DecisionType.MENTOR: "1-ON-1 MENTORING RECOMMENDED",
            DecisionType.REINFORCE: "REINFORCE CORE CONCEPTS",
        }
        dec_title = decision_label_map.get(final_decision.decision, final_decision.decision.value)

        st.markdown(
            f"<div style='background-color:{dec_color}18;border:2px solid {dec_color};padding:18px;border-radius:12px;text-align:center;'>"
            f"<h3 style='color:{dec_color};margin:0;font-weight:700;'>{dec_title}</h3>"
            f"<p style='margin:8px 0 0 0;color:#94a3b8;font-size:14px;'>Strategy: {final_decision.strategy.value.replace('_', ' ').title()}</p>"
            f"</div>",
            unsafe_allow_html=True
        )
        # Dynamic Action Artifact Box based on Decision
        if final_decision.decision == DecisionType.ADVANCE:
            next_t = final_decision.action_payload.get("next_topic", selected_topic)
            st.markdown(
                f"""
                <div style='background-color:#064e3b;border-left:4px solid #10b981;padding:12px;border-radius:6px;margin-top:10px;'>
                    <h5 style='color:#a7f3d0;margin:0;'>🎉 Pathway Action: Curriculum Promotion</h5>
                    <p style='color:#ecfdf5;margin:4px 0 0 0;font-size:13px;'>
                        Mastery confirmed! Next module <b>'{next_t}'</b> is unlocked at <b>{final_decision.target_difficulty.value}</b> difficulty.
                    </p>
                </div>
                """,
                unsafe_allow_html=True
            )
        elif final_decision.decision == DecisionType.REINFORCE:
            focus = ", ".join(final_decision.action_payload.get("focus_topics", [selected_topic]))
            q_count = final_decision.action_payload.get("question_count", 3)
            st.markdown(
                f"""
                <div style='background-color:#450a0a;border-left:4px solid #ef4444;padding:12px;border-radius:6px;margin-top:10px;'>
                    <h5 style='color:#fecaca;margin:0;'>🎯 Pathway Action: Targeted Practice Drill</h5>
                    <p style='color:#fff1f2;margin:4px 0 0 0;font-size:13px;'>
                        Prescribed <b>{q_count} remedial exercises</b> on <b>{focus}</b> at <b>{final_decision.target_difficulty.value}</b> difficulty to solidify core concepts.
                    </p>
                </div>
                """,
                unsafe_allow_html=True
            )
        else:  # MENTOR
            reasons_str = ", ".join([r.replace('_', ' ').title() for r in final_decision.action_payload.get("intervention_reasons", ["Repeated Struggles"])])
            st.markdown(
                f"""
                <div style='background-color:#451a03;border-left:4px solid #f59e0b;padding:12px;border-radius:6px;margin-top:10px;'>
                    <h5 style='color:#fde68a;margin:0;'>🤝 Pathway Action: Human Mentorship Routing</h5>
                    <p style='color:#fffbeb;margin:4px 0 0 0;font-size:13px;'>
                        Cognitive fatigue detected (<b>{reasons_str}</b>). Scheduled 1-on-1 human mentor intervention session to avoid cognitive overload.
                    </p>
                </div>
                """,
                unsafe_allow_html=True
            )

        st.markdown(f"**Action Code:** `{final_decision.suggested_action}`")

    with col_act2:
        st.markdown("#### Execute Database Mutation")
        st.write("Persist this quiz attempt into `quiz_attempts` and apply the AI decision to `students` table in SQLite:")

        if st.button("🚀 Record Attempt & Update Learner Level", type="primary", use_container_width=True):
            try:
                # 1. Record attempt in database
                attempt_res = record_quiz_attempt(
                    student_id=student_id,
                    topic=selected_topic,
                    difficulty=cleaned_sub["difficulty"],
                    score=cleaned_sub["score"],
                    time_spent_seconds=cleaned_sub["time_spent_seconds"],
                    db_path=DB_PATH,
                )

                # 2. Apply level progression in database
                update_res = apply_learning_decision(
                    final_decision,
                    db_path=DB_PATH
                )

                st.success(
                    f"✅ **Learning Pathway Successfully Updated!**\n\n"
                    f"- **Attempt Logged:** Attempt #{attempt_res['attempt_id']} for module '{selected_topic}'\n"
                    f"- **Learner:** {update_res['student_name']}\n"
                    f"- **Level Progression:** `{update_res['previous_level']}` ➡️ `{update_res['new_level']}`\n"
                    f"- **Prescribed Action:** {update_res['action']}"
                )

            except Exception as e:
                st.error(f"Update Error: {e}")

        with st.expander("📋 View Action Execution Payload", expanded=False):
            st.json(final_decision.action_payload)



if __name__ == "__main__":
    run_dashboard()
