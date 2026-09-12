"""Shot generation and management service."""

from oneshot.ai.shot_generator import generate_shots


async def generate(scene: dict, constraints: dict | None = None) -> list[dict]:
    """Generate a shot list from a scene and optional constraints."""
    return await generate_shots(scene, constraints)


def validate_shot(shot: dict) -> bool:
    """Validate that a shot has all required fields."""
    required = ["shot_type", "camera_angle", "lens", "camera_movement", "duration", "action"]
    return all(field in shot for field in required)
