"""
schemas.py — pydantic request models.

These validate and document the JSON the frontend sends. Response bodies are the
engine's own serialized dataclasses (see engine.to_serializable) plus plain DB
dicts, so they aren't modelled here.
"""

from __future__ import annotations

from datetime import date
from typing import List, Optional

from pydantic import BaseModel, Field


class SetIn(BaseModel):
    """One set within a logged session. Identify the exercise by id OR name."""
    exercise_id: Optional[int] = None
    exercise_name: Optional[str] = None
    muscle_group: Optional[str] = None       # used only when creating a new exercise
    equipment: Optional[str] = None
    movement_pattern: Optional[str] = None
    set_number: Optional[int] = None
    reps: int = Field(ge=1)
    weight: float = Field(ge=0)
    rpe: Optional[float] = Field(default=None, ge=1, le=10)


class SessionIn(BaseModel):
    date: date
    notes: Optional[str] = None
    routine_day_id: Optional[int] = None     # which planned day this session was
    sets: List[SetIn] = Field(min_length=1)


class CheckinIn(BaseModel):
    date: date
    sleep_hours: Optional[float] = Field(default=None, ge=0, le=24)
    stress: Optional[int] = Field(default=None, ge=1, le=5)
    body_weight: Optional[float] = Field(default=None, ge=0)
    nutrition: Optional[str] = None          # 'under' | 'enough' | 'over'
    calories: Optional[int] = Field(default=None, ge=0)
    notes: Optional[str] = None


class ExerciseIn(BaseModel):
    name: str = Field(min_length=1)
    muscle_group: Optional[str] = "other"
    equipment: Optional[str] = "barbell"
    movement_pattern: Optional[str] = "other"


class UserIn(BaseModel):
    display_name: str = Field(min_length=1)
    weight_unit: str = "lb"                   # 'lb' | 'kg'
    goal: str = "strength"                     # 'strength' | 'hypertrophy' | 'general'


# ---- Routine setup -------------------------------------------------------

class RoutineExerciseIn(BaseModel):
    exercise_id: int
    target_sets: Optional[int] = Field(default=None, ge=1, le=20)
    target_rep_low: Optional[int] = Field(default=None, ge=1, le=100)
    target_rep_high: Optional[int] = Field(default=None, ge=1, le=100)


class RoutineDayIn(BaseModel):
    label: str = Field(min_length=1)
    exercises: List[RoutineExerciseIn] = Field(default_factory=list)


class RoutineIn(BaseModel):
    name: str = Field(min_length=1)
    source_template_key: Optional[str] = None
    days: List[RoutineDayIn] = Field(min_length=1)
