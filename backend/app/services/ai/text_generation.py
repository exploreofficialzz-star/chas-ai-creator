"""Text generation service using LLMs."""

import json
import re
from typing import List, Dict, Any, Optional

import httpx

from app.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


class TextGenerationService:
    """Service for generating video scripts and text content."""
    
    def __init__(self):
        self.api_key = settings.HUGGINGFACE_API_KEY
        self.api_url = settings.HUGGINGFACE_API_URL
        self.model = settings.TEXT_MODEL
        
        # Scene duration estimates
        self.scene_duration = 3  # seconds per scene
    
    async def generate_script(
        self,
        niche: str,
        video_type: str = "silent",
        duration: int = 30,
        user_instructions: Optional[str] = None,
        style: str = "cinematic",
    ) -> Dict[str, Any]:
        """Generate video script with scenes."""
        
        num_scenes = max(3, duration // self.scene_duration)
        
        prompt = self._build_script_prompt(
            niche=niche,
            video_type=video_type,
            num_scenes=num_scenes,
            user_instructions=user_instructions,
            style=style,
        )
        
        try:
            # Use Hugging Face API
            if self.api_key:
                script_text = await self._call_huggingface_api(prompt)
            else:
                # Fallback to mock generation for development
                script_text = self._generate_mock_script(
                    niche, video_type, num_scenes, style
                )
            
            # Parse script
            script = self._parse_script(script_text, num_scenes)
            
            # Generate narration if needed
            if video_type == "narration":
                script["narration"] = await self._generate_narration(script)
            
            # Generate hashtags
            script["hashtags"] = await self._generate_hashtags(niche, script["title"])
            
            return script
            
        except Exception as e:
            logger.error("Script generation failed", error=str(e))
            # Return fallback script
            return self._generate_fallback_script(niche, num_scenes)
    
    def _build_script_prompt(
        self,
        niche: str,
        video_type: str,
        num_scenes: int,
        user_instructions: Optional[str],
        style: str,
    ) -> str:
        """Build prompt for script generation."""
        
        narration_note = ""
        if video_type == "narration":
            narration_note = "Include engaging narration text for each scene."
        
        instructions_note = ""
        if user_instructions:
            instructions_note = f"Additional instructions: {user_instructions}"
        
        prompt = f"""Create a short-form video script for {niche} content.

Style: {style}
Number of scenes: {num_scenes}
{narration_note}
{instructions_note}

Please provide:
1. A catchy title
2. A brief description
3. Scene-by-scene breakdown with:
   - Scene number
   - Visual description (for image generation)
   - Caption text (short, engaging)
   - Image generation prompt (detailed)

Format as JSON:
{{
    "title": "Video Title",
    "description": "Brief description",
    "scenes": [
        {{
            "scene_number": 1,
            "description": "Visual description",
            "caption": "Caption text",
            "image_prompt": "Detailed image prompt"
        }}
    ]
}}
"""
        return prompt
    
    async def _call_huggingface_api(self, prompt: str) -> str:
        """Call Hugging Face Inference API."""
        
        headers = {"Authorization": f"Bearer {self.api_key}"}
        
        payload = {
            "inputs": prompt,
            "parameters": {
                "max_new_tokens": 1500,
                "temperature": 0.7,
                "return_full_text": False,
            },
        }
        
        model_url = f"{self.api_url}/{self.model}"
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                model_url,
                headers=headers,
                json=payload,
                timeout=60.0,
            )
            response.raise_for_status()
            result = response.json()
            
            if isinstance(result, list) and len(result) > 0:
                return result[0].get("generated_text", "")
            return str(result)
    
    def _parse_script(self, text: str, expected_scenes: int) -> Dict[str, Any]:
        """Parse generated script text into structured format."""
        
        try:
            # Try to extract JSON
            json_match = re.search(r'\{.*\}', text, re.DOTALL)
            if json_match:
                script = json.loads(json_match.group())
                return script
        except json.JSONDecodeError:
            pass
        
        # Fallback parsing
        return self._fallback_parse_script(text, expected_scenes)
    
    def _fallback_parse_script(self, text: str, num_scenes: int) -> Dict[str, Any]:
        """Fallback script parsing."""
        lines = text.strip().split('\n')
        
        script = {
            "title": "Generated Video",
            "description": "AI-generated video content",
            "scenes": [],
        }
        
        current_scene = None
        for line in lines:
            line = line.strip()
            if line.startswith('Title:'):
                script["title"] = line.replace('Title:', '').strip()
            elif line.startswith('Scene') and ':' in line:
                if current_scene:
                    script["scenes"].append(current_scene)
                current_scene = {
                    "scene_number": len(script["scenes"]) + 1,
                    "description": line.split(':', 1)[1].strip(),
                    "caption": "",
                    "image_prompt": "",
                }
            elif current_scene and line:
                if not current_scene["caption"]:
                    current_scene["caption"] = line
                else:
                    current_scene["image_prompt"] += line + " "
        
        if current_scene:
            script["scenes"].append(current_scene)
        
        # Ensure minimum scenes
        while len(script["scenes"]) < num_scenes:
            script["scenes"].append({
                "scene_number": len(script["scenes"]) + 1,
                "description": f"Scene {len(script['scenes']) + 1}",
                "caption": "",
                "image_prompt": "",
            })
        
        return script
    
    async def _generate_narration(self, script: Dict[str, Any]) -> str:
        """Generate narration text from script."""
        scenes = script.get("scenes", [])
        narration_parts = []
        
        for scene in scenes:
            caption = scene.get("caption", "")
            if caption:
                narration_parts.append(caption)
        
        return " ".join(narration_parts)
    
    async def _generate_hashtags(self, niche: str, title: str) -> List[str]:
        """Generate relevant hashtags."""
        
        niche_hashtags = {
            "animals": ["#animals", "#pets", "#cute", "#animalsoftiktok", "#petlover"],
            "tech": ["#tech", "#technology", "#innovation", "#gadgets", "#ai"],
            "cooking": ["#cooking", "#food", "#recipe", "#foodie", "#homemade"],
            "motivation": ["#motivation", "#inspiration", "#success", "#mindset", "#goals"],
            "fitness": ["#fitness", "#workout", "#gym", "#health", "#exercise"],
            "travel": ["#travel", "#adventure", "#wanderlust", "#explore", "#vacation"],
            "gaming": ["#gaming", "#gamer", "#videogames", "#gameplay", "#streamer"],
            "education": ["#education", "#learning", "#knowledge", "#study", "#facts"],
            "comedy": ["#comedy", "#funny", "#humor", "#lol", "#meme"],
            "music": ["#music", "#song", "#musician", "#artist", "#newmusic"],
        }
        
        hashtags = niche_hashtags.get(niche.lower(), ["#viral", "#trending", "#fyp"])
        
        # Add title-based hashtag
        title_words = title.lower().split()[:3]
        for word in title_words:
            word = re.sub(r'[^\w]', '', word)
            if len(word) > 3:
                hashtags.append(f"#{word}")
        
        return hashtags[:10]  # Limit to 10 hashtags
    
    def _generate_mock_script(
        self,
        niche: str,
        video_type: str,
        num_scenes: int,
        style: str,
    ) -> str:
        """Generate mock script for development."""
        
        templates = {
            "animals": {
                "title": "Adorable Animal Moments That Will Melt Your Heart",
                "scenes": [
                    "A fluffy golden retriever puppy playing in a sunny meadow",
                    "A curious cat peeking out from behind a colorful flower pot",
                    "A baby elephant splashing water with its trunk",
                    "A group of penguins waddling on an icy landscape",
                ],
            },
            "tech": {
                "title": "The Future of Technology is Here",
                "scenes": [
                    "Futuristic holographic interface displaying data",
                    "Robot arm assembling electronics in a high-tech factory",
                    "Person wearing advanced VR headset in a virtual world",
                    "Smart home devices connected in a modern apartment",
                ],
            },
            "cooking": {
                "title": "Quick and Delicious Recipe You Need to Try",
                "scenes": [
                    "Fresh ingredients beautifully arranged on a wooden board",
                    "Chef's hands skillfully chopping colorful vegetables",
                    "Steam rising from a sizzling pan with delicious food",
                    "Perfectly plated dish with garnishes and herbs",
                ],
            },
            "motivation": {
                "title": "Believe in Yourself and Anything is Possible",
                "scenes": [
                    "Person standing on a mountain peak at sunrise",
                    "Hands writing goals in a beautiful journal",
                    "Athlete pushing through a challenging workout",
                    "Successful person celebrating an achievement",
                ],
            },
        }
        
        template = templates.get(niche, templates["motivation"])
        
        scenes = []
        for i in range(min(num_scenes, len(template["scenes"]))):
            scenes.append({
                "scene_number": i + 1,
                "description": template["scenes"][i],
                "caption": f"Scene {i + 1}: {template['scenes'][i]}",
                "image_prompt": f"{style} style, {template['scenes'][i]}, high quality, detailed, cinematic lighting",
            })
        
        return json.dumps({
            "title": template["title"],
            "description": f"An engaging {niche} video in {style} style",
            "scenes": scenes,
        })
    
    def _generate_fallback_script(self, niche: str, num_scenes: int) -> Dict[str, Any]:
        """Generate fallback script when AI fails."""
        scenes = []
        for i in range(num_scenes):
            scenes.append({
                "scene_number": i + 1,
                "description": f"Scene {i + 1} for {niche} content",
                "caption": f"Engaging moment {i + 1}",
                "image_prompt": f"High quality image for {niche} content, scene {i + 1}",
            })
        
        return {
            "title": f"Amazing {niche.title()} Content",
            "description": f"Discover amazing {niche} moments",
            "scenes": scenes,
            "hashtags": [f"#{niche}", "#viral", "#trending"],
      }
