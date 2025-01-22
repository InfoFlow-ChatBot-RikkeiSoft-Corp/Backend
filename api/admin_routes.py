from flask_restx import Namespace, Resource, fields, reqparse
from flask import request, jsonify
from datetime import datetime
from models.models import LLMPrompt, db
from pytz import timezone

# Namespace 생성
admin_ns = Namespace('admin', description='Admin operations for managing LLM prompts')

# Swagger 모델 정의
prompt_model = admin_ns.model('LLMPrompt', {
    'id': fields.Integer(description='Prompt ID'),
    'name': fields.String(description='Prompt name'),
    'text': fields.String(description='Prompt text'),
    'is_active': fields.Boolean(description='Is this prompt active?')
})

new_prompt_model = admin_ns.model('NewLLMPrompt', {
    'prompt_name': fields.String(required=True, description='Name of the prompt'),
    'prompt_text': fields.String(required=True, description='Text of the prompt'),
    'created_by': fields.String(required=True, description='Username of the creator')
})

update_prompt_model = admin_ns.model('UpdateLLMPrompt', {
    'prompt_name': fields.String(description='Updated name of the prompt'),
    'prompt_text': fields.String(description='Updated text of the prompt'),
    'updated_by': fields.String(description='Username of the updater')
})


tz = timezone("Asia/Ho_Chi_Minh")  # Replace with your desired time zone
current_time = datetime.now(tz)

@admin_ns.route('/prompts')
class GetAllPrompts(Resource):
    @admin_ns.response(200, 'Success', model=[prompt_model])
    def get(self):
        """Retrieve all prompts"""
        prompts = LLMPrompt.query.all()
        return [{"id": p.id, "name": p.prompt_name, "text": p.prompt_text, "is_active": p.is_active} for p in prompts]

@admin_ns.route('/prompt/<int:id>')
class GetPrompt(Resource):
    @admin_ns.response(200, 'Success', model=prompt_model)
    @admin_ns.response(404, 'Prompt not found')
    def get(self, id):
        """Retrieve a specific prompt by ID"""
        prompt = LLMPrompt.query.get(id)
        if not prompt:
            return {"error": "Prompt not found"}, 404
        return {"name": prompt.prompt_name, "text": prompt.prompt_text}

@admin_ns.route('/prompt')
class AddPrompt(Resource):
    @admin_ns.expect(new_prompt_model)
    @admin_ns.response(201, 'Prompt added successfully')
    @admin_ns.response(400, 'Bad Request')
    def post(self):
        """Add a new prompt"""
        try:
            print("\n=== 🆕 Adding New Prompt ===")
            data = request.get_json()
            print(f"Received data: {data}")
            
            # Validate required fields
            if not all(key in data for key in ['prompt_name', 'prompt_text', 'created_by']):
                print("❌ Missing required fields")
                return {"error": "Missing required fields"}, 400

            # Generate unique name if 'New Prompt' is provided
            base_name = data["prompt_name"]
            prompt_name = base_name
            counter = 1

            while LLMPrompt.query.filter_by(prompt_name=prompt_name).first():
                prompt_name = f"{base_name} ({counter})"
                counter += 1
                print(f"Trying alternative name: {prompt_name}")

            print(f"Creating new prompt with name: {prompt_name}")
            new_prompt = LLMPrompt(
                prompt_name=prompt_name,  # Use the unique name
                prompt_text=data["prompt_text"],
                created_by=data["created_by"],
                created_at=current_time,
                is_active=False  # Set default to inactive
            )
            
            db.session.add(new_prompt)
            db.session.commit()
            
            print(f"✅ Prompt '{prompt_name}' added successfully")
            return {
                "message": "Prompt added successfully",
                "prompt": {
                    "id": new_prompt.id,
                    "name": prompt_name,
                    "text": new_prompt.prompt_text,
                    "is_active": new_prompt.is_active
                }
            }, 201
            
        except Exception as e:
            print(f"❌ Error adding prompt: {str(e)}")
            db.session.rollback()
            return {"error": f"Failed to add prompt: {str(e)}"}, 500

@admin_ns.route('/prompt/activate/<int:id>')
class ActivatePrompt(Resource):
    @admin_ns.response(200, 'Prompt activated successfully')
    @admin_ns.response(404, 'Prompt not found')
    def post(self, id):
        """Activate a specific prompt by ID"""
        prompts = LLMPrompt.query.all()
        for p in prompts:
            p.is_active = False  # Deactivate all prompts
        prompt = LLMPrompt.query.get(id)
        if not prompt:
            return {"error": "Prompt not found"}, 404
        prompt.is_active = True  # Activate selected prompt
        db.session.commit()
        return {"message": f"{prompt.prompt_name} prompt has been activated."}, 200
    
@admin_ns.route('/prompt/<int:id>')
class PromptOperations(Resource):
    @admin_ns.expect(update_prompt_model)
    @admin_ns.response(200, 'Prompt updated successfully')
    @admin_ns.response(404, 'Prompt not found')
    def put(self, id):
        """Update an existing prompt by ID"""
        data = request.get_json()
        prompt = LLMPrompt.query.get(id)
        if not prompt:
            return {"error": "Prompt not found"}, 404
        
        # Update fields only if they are provided
        prompt.prompt_name = data.get("prompt_name", prompt.prompt_name)
        prompt.prompt_text = data.get("prompt_text", prompt.prompt_text)
        prompt.updated_by = data.get("updated_by", prompt.updated_by)
        prompt.updated_at = current_time
        db.session.commit()
        return {"message": "Prompt updated successfully"}, 200

    @admin_ns.response(200, 'Prompt deleted successfully')
    @admin_ns.response(404, 'Prompt not found')
    def delete(self, id):
        """Delete a specific prompt by ID"""
        prompt = LLMPrompt.query.get(id)
        if not prompt:
            return {"error": "Prompt not found"}, 404

        db.session.delete(prompt)
        db.session.commit()
        return {"message": "Prompt deleted successfully"}, 200
