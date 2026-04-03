import importlib.util
import json
from pathlib import Path


PLUGIN_PATH = Path("/home/fati_hermes/.hermes/plugins/fati-mini-control/__init__.py")


def load_plugin_module():
    spec = importlib.util.spec_from_file_location("test_fati_mini_control_plugin", PLUGIN_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def configure_tmp_state(module, tmp_path):
    module.STATE_PATH = tmp_path / "state.json"
    module.LOCK_PATH = tmp_path / "state.lock"


def test_fati_task_add_prefers_args_dict_over_runtime_kwargs(tmp_path):
    plugin = load_plugin_module()
    configure_tmp_state(plugin, tmp_path)

    raw = plugin.fati_task_add(
        {
            "title": "Corregir bridge Telegram",
            "description": "Debe guardar campos reales",
            "source": "telegram",
            "priority": "high",
        },
        task_id="20260401_runtime_internal",
    )
    task = json.loads(raw)

    assert task["id"] == "TASK ID 0001"
    assert task["title"] == "Corregir bridge Telegram"
    assert task["description"] == "Debe guardar campos reales"
    assert task["priority"] == "high"
    assert not task["title"].startswith("{'title':")


def test_fati_task_status_ignores_runtime_task_id_kw_when_args_dict_has_real_id(tmp_path):
    plugin = load_plugin_module()
    configure_tmp_state(plugin, tmp_path)
    plugin.add_task("Tarea de prueba", source="local")

    raw = plugin.fati_task_status(
        {"task_id": "TASK ID 0001", "status": "in_progress", "source": "local"},
        task_id="20260401_runtime_internal",
    )
    task = json.loads(raw)

    assert task["id"] == "TASK ID 0001"
    assert task["status"] == "in_progress"


def test_fati_task_log_ignores_runtime_task_id_kw_when_args_dict_has_real_id(tmp_path):
    plugin = load_plugin_module()
    configure_tmp_state(plugin, tmp_path)
    plugin.add_task("Tarea de prueba", source="local")

    raw = plugin.fati_task_log(
        {"task_id": "TASK ID 0001", "line": "log real", "source": "local"},
        task_id="20260401_runtime_internal",
    )
    task = json.loads(raw)

    assert task["id"] == "TASK ID 0001"
    assert task["logs"][-1]["line"] == "log real"
