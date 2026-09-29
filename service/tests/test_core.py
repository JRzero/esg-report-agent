from datetime import date
from app.core.permissions import allows
from app.modules.services import semantic_key

def test_permissions():
    assert allows('OWNER','MANAGE_MEMBERS')
    assert allows('EDITOR','EDIT_REPORT')
    assert not allows('REVIEWER','EDIT_REPORT')
    assert not allows('CLIENT_MEMBER','MANAGE_MEMBERS')

def test_semantic_key_stable():
    a=semantic_key('EMPLOYEE_TOTAL','x',date(2026,1,1),date(2026,12,31),'GROUP',{'gender':'female','region':'CN'})
    b=semantic_key('EMPLOYEE_TOTAL','x',date(2026,1,1),date(2026,12,31),'GROUP',{'region':'CN','gender':'female'})
    assert a==b
