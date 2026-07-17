def create_resume_and_job(client):
    resume = client.post(
        "/api/resumes",
        json={
            "title": "运营简历",
            "target_role": "短视频运营",
            "content": "负责短视频选题、剪辑与数据复盘，单条播放量达到2000。",
        },
    ).json()
    job = client.post(
        "/api/jobs",
        json={
            "title": "短视频运营实习生",
            "company_name": "测试公司",
            "description": "负责选题策划、账号维护、数据分析和直播协作。",
        },
    ).json()
    return resume, job


def test_full_interview_is_contextual_and_idempotent(client):
    resume, job = create_resume_and_job(client)
    created = client.post(
        "/api/interviews",
        json={
            "resume_id": resume["id"],
            "job_id": job["id"],
            "interview_type": "comprehensive",
            "pressure_level": "challenging",
            "question_count": 3,
        },
    )
    assert created.status_code == 201
    session_id = created.json()["session"]["id"]
    assert created.json()["session"]["resume_title_snapshot"] == "运营简历"

    started = client.post(f"/api/interviews/{session_id}/start")
    repeated_start = client.post(f"/api/interviews/{session_id}/start")
    assert started.status_code == 200
    assert len(started.json()["turns"]) == 1
    assert len(repeated_start.json()["turns"]) == 1
    assert "短视频运营实习生" in started.json()["turns"][0]["content"]

    answers = [
        "我负责短视频选题和剪辑，通过复盘完播率调整前3秒，播放量提升到2000。",
        "背景是账号更新不稳定，目标是每周发布3条。我建立选题表并跟踪结果，最终按期完成。",
        "我会先核对曝光、点击和转化数据，再检查素材、人群和承接环节。",
    ]
    last = None
    for index, content in enumerate(answers):
        last = client.post(
            f"/api/interviews/{session_id}/answers",
            json={"content": content, "request_id": f"answer-request-{index}"},
        )
        assert last.status_code == 200

    payload = last.json()
    assert payload["session"]["status"] == "completed"
    assert payload["report"]["overall_score"] > 0
    assert len(payload["report"]["evidence"]) >= 3
    assert len([turn for turn in payload["turns"] if turn["role"] == "candidate"]) == 3

    duplicate = client.post(
        f"/api/interviews/{session_id}/answers",
        json={"content": answers[-1], "request_id": "answer-request-2"},
    )
    assert duplicate.status_code == 200
    assert len(duplicate.json()["turns"]) == len(payload["turns"])

    repeated_complete = client.post(f"/api/interviews/{session_id}/complete")
    assert repeated_complete.status_code == 200
    assert repeated_complete.json()["report"]["id"] == payload["report"]["id"]


def test_resume_text_upload_creates_resume_version(client):
    response = client.post(
        "/api/resume-uploads",
        data={"title": "上传简历", "target_role": "直播运营"},
        files={
            "file": (
                "resume.txt",
                "教育背景\n项目经历\n负责直播设备调试、场控和下播数据复盘。".encode("utf-8"),
                "text/plain",
            )
        },
    )
    assert response.status_code == 201
    result = response.json()
    assert result["title"] == "上传简历"
    assert result["extracted_characters"] >= 20
    resume = client.get(f"/api/resumes/{result['resume_id']}").json()
    assert "直播设备调试" in resume["content"]


def test_invalid_interview_configuration_is_rejected(client):
    response = client.post(
        "/api/interviews",
        json={"question_count": 2, "target_role": ""},
    )
    assert response.status_code == 422


def test_audio_transcription_uses_local_fallback_without_openai(client, monkeypatch):
    from app.api.routes import interview_audio

    monkeypatch.setattr(interview_audio.settings, "ai_provider", "local")
    monkeypatch.setattr(
        interview_audio,
        "transcribe_locally",
        lambda content, filename: "这是语音回答文字",
    )
    response = client.post(
        "/api/interview-audio/transcriptions",
        files={"file": ("answer.webm", b"mock-audio-content", "audio/webm")},
    )
    assert response.status_code == 200
    assert response.json()["text"] == "这是语音回答文字"
    assert response.json()["engine"].startswith("local:")
