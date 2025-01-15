from flask import Blueprint, request, jsonify
from datetime import datetime
from models.models import LLMPrompt, db
from pytz import timezone

admin_bp = Blueprint("admin", __name__)
tz = timezone("Asia/Ho_Chi_Minh")  # Replace with your desired time zone
current_time = datetime.now(tz)

# 모든 프롬프트 가져오기
@admin_bp.route("/prompts", methods=["GET"])
def get_all_prompts():
    prompts = LLMPrompt.query.all()
    return jsonify([{"id": p.id, "name": p.prompt_name, "text": p.prompt_text, "is_active": p.is_active} for p in prompts])

# 특정 프롬프트 가져오기
@admin_bp.route("/prompt/<int:id>", methods=["GET"])
def get_prompt(id):
    prompt = LLMPrompt.query.get(id)
    if not prompt:
        return jsonify({"error": "Prompt not found"}), 404
    return jsonify({"name": prompt.prompt_name, "text": prompt.prompt_text})

# 새 프롬프트 추가
@admin_bp.route("/prompt", methods=["POST"])
def add_prompt():
    data = request.get_json()
    new_prompt = LLMPrompt(
        prompt_name=data["prompt_name"],
        prompt_text=data["prompt_text"],
        created_by=data["created_by"]
    )
    db.session.add(new_prompt)
    db.session.commit()
    return jsonify({"message": "Prompt added successfully"}), 201

# 기존 프롬프트 업데이트
@admin_bp.route("/prompt/<int:id>", methods=["PUT"])
def update_prompt(id):
    data = request.get_json()
    prompt = LLMPrompt.query.get(id)
    if not prompt:
        return jsonify({"error": "Prompt not found"}), 404

    prompt.prompt_text = data.get("prompt_text", prompt.prompt_text)
    prompt.updated_by = data.get("updated_by", prompt.updated_by)
    prompt.updated_at = current_time
    db.session.commit()
    return jsonify({"message": "Prompt updated successfully"}), 200

# 프롬프트 활성화
@admin_bp.route("/prompt/activate/<int:id>", methods=["POST"])
def activate_prompt(id):
    prompts = LLMPrompt.query.all()
    for p in prompts:
        p.is_active = False  # 모든 프롬프트 비활성화
    prompt = LLMPrompt.query.get(id)
    if not prompt:
        return jsonify({"error": "Prompt not found"}), 404
    prompt.is_active = True  # 선택한 프롬프트 활성화
    db.session.commit()
    return jsonify({"message": f"{prompt.prompt_name} 프롬프트가 활성화되었습니다."}), 200
