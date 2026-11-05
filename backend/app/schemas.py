from typing import List, Literal, Optional
from pydantic import BaseModel, Field, StrictInt, StrictStr, validator


class StrictModel(BaseModel):
    class Config:
        extra = 'forbid'


class SampleRequest(StrictModel):
    sampleId: StrictStr


class Action(StrictModel):
    type: Literal['set_target', 'lock', 'unlock', 'delete', 'restore', 'restore_all', 'apply_proposal', 'undo']
    blockIds: List[StrictStr] = Field(default_factory=list, max_items=500)
    targetMs: Optional[StrictInt] = None
    proposalId: Optional[StrictStr] = None


class ActionRequest(StrictModel):
    expectedRevision: StrictInt
    action: Action


class ProposalRequest(StrictModel):
    expectedRevision: StrictInt
    mode: Literal['auto', 'rules'] = 'auto'


class RenderRequest(StrictModel):
    expectedRevision: StrictInt
    allowOverTarget: bool = False


class ModelItem(StrictModel):
    blockId: StrictStr
    importance: int = Field(ge=0, le=100)
    suggestedAction: Literal['keep', 'delete', 'review']
    reason: str = Field(max_length=200)
    riskHints: List[Literal['condition', 'negation', 'number', 'context']] = Field(default_factory=list, max_items=4)


class ModelAnswer(StrictModel):
    items: List[ModelItem] = Field(max_items=500)
    reviewNotes: List[str] = Field(default_factory=list, max_items=12)

    @validator('reviewNotes', each_item=True)
    def notes_are_bounded(cls, value):
        if len(value) > 400:
            raise ValueError('说明过长')
        return value
