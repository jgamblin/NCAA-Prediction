import os
from config.model_params_loader import load_model_params


def test_returns_dict_even_if_missing():
    missing_path = os.path.join(os.path.dirname(__file__), 'DOES_NOT_EXIST.json')
    params = load_model_params(missing_path)
    assert isinstance(params, dict)
    assert params == {}


def test_load_default_path():
    params = load_model_params()
    assert isinstance(params, dict)
    if params:
        assert 'simple_predictor' in params
