from pathlib import Path
from types import SimpleNamespace
import streamlit as st
from streamlit.testing.v1 import AppTest

APP=Path(__file__).resolve().parents[1]/'app.py'


def test_default_tabs_filters_reset_and_trend():
    app=AppTest.from_file(APP).run(timeout=30)
    assert not app.exception
    assert len(app.tabs)==4 and len(app.metric)==5
    original=app.metric[0].value
    app.multiselect[0].set_value(['Instagram']).run()
    assert not app.exception and app.metric[0].value!=original
    app.text_input[0].set_value('does not exist').run()
    assert not app.exception
    app.selectbox[0].set_value('ROI').run()
    assert not app.exception
    app.multiselect[0].set_value([]).run()
    assert not app.exception
    assert len([message for message in app.info if 'No data for selected filters' in message.value])==4
    next(button for button in app.button if button.label=='Reset Filters').click().run()
    assert not app.exception and app.metric[0].value==original


def test_bad_upload_replaces_default_without_crash(monkeypatch):
    upload=SimpleNamespace(name='bad.csv',getvalue=lambda:b'Date,Clicks\ninvalid,nope')
    monkeypatch.setattr(st,'file_uploader',lambda *a,**k:upload)
    app=AppTest.from_file(APP).run(timeout=30)
    assert not app.exception
    assert len(app.tabs)==4 and len(app.metric)==0
