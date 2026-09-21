"""Small smoke tests for the read-only M3 Streamlit explorer helpers."""
import numpy as np


def test_ui_module_import_and_saved_players():
    from app.model_explorer import load_artifacts
    artifacts = load_artifacts()
    names = [row["player_name"] for row in artifacts["seasons"]]
    assert len(names) == 18
    assert any("wirtz" in name.casefold() for name in names)
    assert len(artifacts["feature_order"]) == 15


def test_existing_player_similarity_excludes_self():
    from app.model_explorer import load_artifacts, nearest_players
    artifacts = load_artifacts()
    selected = next(row for row in artifacts["seasons"] if "wirtz" in row["player_name"].casefold())
    nearest = nearest_players(selected, artifacts["seasons"], artifacts["similarity"],
                              artifacts["scaler"]["latent_train_mean"])
    assert len(nearest) == 17
    assert all(row["player_id"] != selected["player_id"] for row in nearest)
    assert nearest[0]["rank"] == 1


def test_custom_feature_inference_uses_existing_api():
    from app.model_explorer import build_custom_defaults, load_artifacts
    from src.models.inference import encode_player_match
    artifacts = load_artifacts()
    values = build_custom_defaults(artifacts)
    result = encode_player_match(values)
    assert len(result["embedding"]) == 4
    assert isinstance(result["prototype_comparisons"], list)
    assert np.isfinite(result["embedding"]).all()


def test_embedding_figure_and_out_of_range_preset():
    from app.model_explorer import build_custom_defaults, load_artifacts, make_embedding_figure
    artifacts = load_artifacts()
    selected = next(row for row in artifacts["seasons"] if "wirtz" in row["player_name"].casefold())
    figure, projection, selected_index = make_embedding_figure(artifacts["seasons"], selected["player_id"])
    assert projection.shape == (18, 2)
    assert selected_index is not None
    assert len(figure.axes) == 1
    defaults = build_custom_defaults(artifacts)
    feature = artifacts["feature_order"][0]
    defaults[feature] = artifacts["scaler"]["train_max"][0] + 1
    assert defaults[feature] > artifacts["scaler"]["train_max"][0]
