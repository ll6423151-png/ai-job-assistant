from datetime import datetime, timezone
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.interview import InterviewReport, InterviewSession, InterviewTurn
from app.services.interview_provider import LocalInterviewProvider, get_interview_provider

async def list_turns(db: AsyncSession, session_id: int) -> list[InterviewTurn]:
    return list((await db.scalars(select(InterviewTurn).where(InterviewTurn.session_id == session_id).order_by(InterviewTurn.sequence, InterviewTurn.id))).all())

async def get_report(db: AsyncSession, session_id: int) -> InterviewReport | None:
    return await db.scalar(select(InterviewReport).where(InterviewReport.session_id == session_id))

async def start_interview(db: AsyncSession, session: InterviewSession) -> None:
    if session.status != 'configured':
        return
    provider = get_interview_provider()
    try:
        question = provider.generate_question(session, [])
    except Exception:
        provider = LocalInterviewProvider()
        question = provider.generate_question(session, [])
    session.provider_name = provider.name
    session.status = 'in_progress'
    session.started_at = datetime.now(timezone.utc)
    db.add(InterviewTurn(session_id=session.id, sequence=1, role='interviewer', kind='question', content=question, pressure_signal=False))
    await db.commit()

async def submit_answer(db: AsyncSession, session: InterviewSession, content: str, request_id: str | None) -> None:
    if request_id:
        duplicate = await db.scalar(select(InterviewTurn).where(InterviewTurn.session_id == session.id, InterviewTurn.request_id == request_id))
        if duplicate:
            return
    turns = await list_turns(db, session.id)
    answer_count = sum((turn.role == 'candidate' for turn in turns))
    db.add(InterviewTurn(session_id=session.id, sequence=len(turns) + 1, role='candidate', kind='answer', content=content, request_id=request_id, pressure_signal=False))
    await db.flush()
    if answer_count + 1 >= session.question_count:
        await complete_interview(db, session)
        return
    turns = await list_turns(db, session.id)
    provider = get_interview_provider()
    try:
        question = provider.generate_question(session, turns)
    except Exception:
        provider = LocalInterviewProvider()
        question = provider.generate_question(session, turns)
    session.provider_name = provider.name
    db.add(InterviewTurn(session_id=session.id, sequence=len(turns) + 1, role='interviewer', kind='question', content=question, pressure_signal=session.pressure_level != 'standard'))
    await db.commit()

async def complete_interview(db: AsyncSession, session: InterviewSession) -> InterviewReport:
    existing = await get_report(db, session.id)
    if existing:
        if session.status != 'completed':
            session.status = 'completed'
            session.completed_at = session.completed_at or datetime.now(timezone.utc)
            await db.commit()
        return existing
    turns = await list_turns(db, session.id)
    provider = get_interview_provider()
    try:
        report_data = provider.generate_report(session, turns)
    except Exception:
        provider = LocalInterviewProvider()
        report_data = provider.generate_report(session, turns)
    report = InterviewReport(session_id=session.id, **report_data.__dict__)
    session.provider_name = provider.name
    session.status = 'completed'
    session.completed_at = datetime.now(timezone.utc)
    db.add(report)
    await db.commit()
    await db.refresh(report)
    return report
