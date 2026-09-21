"""Minimal Streamlit explorer for the saved Alonso Tactical Role Encoder v1.

This module only reads saved M3 artifacts and delegates custom encoding to
``src.models.inference``. It never trains a model, collects data, or creates
new tactical features.
"""
from __future__ import annotations

import csv
import json
import warnings
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = ROOT / "outputs" / "alonso_tactical_encoder_v1"
MODEL_DIR = ROOT / "models" / "alonso_tactical_encoder_v1"


def _read_csv(name: str) -> list[dict[str, str]]:
    path = OUTPUT_DIR / name
    if not path.is_file():
        raise FileNotFoundError(f"Required output file is missing: {path}")
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def load_artifacts() -> dict:
    """Load the saved model explorer inputs without hard-coded player names."""
    required = [
        OUTPUT_DIR / "player_season_embeddings.csv",
        OUTPUT_DIR / "player_similarity_matrix.csv",
        OUTPUT_DIR / "role_prototypes_v1.csv",
        OUTPUT_DIR / "metrics.json",
        MODEL_DIR / "feature_order.json",
        MODEL_DIR / "scaler.json",
        MODEL_DIR / "encoder.pt",
    ]
    missing = [str(path) for path in required if not path.is_file()]
    if missing:
        raise FileNotFoundError("Missing model explorer artifacts: " + ", ".join(missing))
    feature_order = json.loads((MODEL_DIR / "feature_order.json").read_text(encoding="utf-8"))
    scaler = json.loads((MODEL_DIR / "scaler.json").read_text(encoding="utf-8"))
    metrics = json.loads((OUTPUT_DIR / "metrics.json").read_text(encoding="utf-8"))
    seasons = _read_csv("player_season_embeddings.csv")
    similarity_rows = _read_csv("player_similarity_matrix.csv")
    prototypes = _read_csv("role_prototypes_v1.csv")
    for row in seasons:
        for key in ("matches", "minutes", "z1_mean", "z2_mean", "z3_mean", "z4_mean"):
            row[key] = float(row[key])
        row["matches"] = int(row["matches"])
    for row in similarity_rows:
        for key, value in list(row.items()):
            if key not in ("player_id", "player_name"):
                row[key] = float(value) if value else None
    for row in prototypes:
        row["n_rows"] = int(row["n_rows"])
        row["n_players"] = int(row["n_players"])
        for key in ("z1", "z2", "z3", "z4"):
            row[key] = float(row[key])
    return dict(feature_order=feature_order, scaler=scaler, metrics=metrics,
                seasons=seasons, similarity=similarity_rows, prototypes=prototypes)


def _embedding(row: dict) -> np.ndarray:
    return np.array([row[f"z{i}_mean"] for i in range(1, 5)], dtype=float)


def nearest_players(selected: dict, seasons: list[dict], similarity_rows: list[dict], train_center: list[float]) -> list[dict]:
    """Use the saved player cosine table and compute 4-D Euclidean cross-checks."""
    selected_id = selected["player_id"]
    similarity_row = next(row for row in similarity_rows if row["player_id"] == selected_id)
    selected_vector = _embedding(selected)
    results = []
    for row in seasons:
        if row["player_id"] == selected_id:
            continue
        cosine = similarity_row.get(row["player_id"])
        centred_distance = float(np.linalg.norm((_embedding(row) - np.asarray(train_center)) -
                                                 (selected_vector - np.asarray(train_center))))
        results.append(dict(player_id=row["player_id"], player_name=row["player_name"],
                            matches=row["matches"], cosine_similarity=cosine,
                            euclidean_distance=centred_distance))
    results.sort(key=lambda row: (row["cosine_similarity"] is None,
                                  -(row["cosine_similarity"] or 0.0), row["player_name"]))
    for rank, row in enumerate(results, 1):
        row["rank"] = rank
    return results


def prototype_comparison(embedding: list[float], prototypes: list[dict], train_center: list[float]) -> list[dict]:
    """Use the existing inference comparison contract for saved prototypes."""
    from src.models.inference import compare_to_role_prototypes

    # The public API reads the saved prototype artifact and uses the saved
    # train-centred latent reference. Keep this helper's prototype argument as
    # a validation/display contract for the UI and avoid duplicate geometry.
    if not prototypes:
        return []
    return compare_to_role_prototypes(embedding)


def _season_feature_means(player_name: str, feature_order: list[str]) -> dict[str, float] | None:
    """Read optional M2 feature means for the selected-player custom preset."""
    path = ROOT / "outputs" / "alonso_team_role_space" / "player_season_role_vectors.csv"
    if not path.is_file():
        return None
    with path.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            if row.get("player_name") == player_name:
                return {feature: float(row[f"{feature}_mean"]) for feature in feature_order}
    return None


def build_custom_defaults(artifacts: dict, player_name: str | None = None) -> dict[str, float]:
    """Return raw feature values from the train mean or selected player mean."""
    defaults = dict(zip(artifacts["feature_order"], artifacts["scaler"]["mean"]))
    if player_name:
        player_defaults = _season_feature_means(player_name, artifacts["feature_order"])
        if player_defaults:
            defaults.update(player_defaults)
    return defaults


def make_embedding_figure(seasons: list[dict], selected_player_id: str):
    """Create the visualization-only PCA projection of season embeddings."""
    import matplotlib.pyplot as plt
    from sklearn.decomposition import PCA

    vectors = np.array([_embedding(row) for row in seasons], dtype=float)
    projection = PCA(n_components=2, svd_solver="full").fit_transform(vectors)
    fig, ax = plt.subplots(figsize=(9, 5.5))
    selected_index = None
    for index, (row, point) in enumerate(zip(seasons, projection)):
        selected = row["player_id"] == selected_player_id
        if selected:
            selected_index = index
        ax.scatter(point[0], point[1], s=180 if selected else 55,
                   color="#d946ef" if selected else "#2563eb",
                   edgecolor="#111827" if selected else "white", linewidth=1.2,
                   alpha=0.95 if selected else 0.75, zorder=3 if selected else 2)
        if selected:
            ax.annotate(row["player_name"], point, xytext=(7, 7), textcoords="offset points",
                        fontsize=10, weight="bold")
    ax.set_xlabel("Embedding projection PC1")
    ax.set_ylabel("Embedding projection PC2")
    ax.grid(alpha=0.2)
    ax.set_title("Player season embeddings")
    fig.tight_layout()
    return fig, projection, selected_index


def _render() -> None:
    import streamlit as st

    st.set_page_config(page_title="Alonso Tactical Role Encoder v1", layout="wide")
    st.title("Xabi Alonso Tactical Role Encoder v1")
    st.caption("Experimental baseline trained only on 2023/24 Bayer Leverkusen data. "
               "Similarity means observed tactical behaviour similarity, not player quality or transfer suitability.")
    try:
        artifacts = load_artifacts()
    except (FileNotFoundError, json.JSONDecodeError, ValueError) as exc:
        st.error(f"Model explorer could not load its saved artifacts: {exc}")
        st.stop()

    seasons = artifacts["seasons"]
    names = [row["player_name"] for row in seasons]
    wirtz_index = next((i for i, name in enumerate(names) if "wirtz" in name.casefold()), 0)
    selected_index = st.session_state.get("selected_player_index", wirtz_index)
    mode = st.radio("Mode", ["Existing Player", "Custom Tactical Features"], horizontal=True)

    with st.sidebar:
        st.subheader("Model information")
        dataset = artifacts["metrics"]["dataset"]
        config = artifacts["metrics"]["config"]
        robustness = artifacts["metrics"]["robustness"]
        seed42 = artifacts["metrics"]["runs"][0]["test"]
        st.write("Architecture: 15 → 12 → 8 → 4 → 8 → 12 → 15")
        st.write("Latent dimensions: 4")
        st.write(f"Training data: {dataset['rows']} player-match rows, {dataset['matches']} matches, {dataset['players']} players")
        st.metric("Autoencoder test MSE", f"{seed42['ae']['mse']:.4f}")
        st.metric("PCA test MSE", f"{seed42['pca']['mse']:.4f}")
        st.metric("Autoencoder neighbour preservation", f"{robustness['metrics']['neighbour_overlap']['ae']['mean']:.3f}")
        st.metric("PCA neighbour preservation", f"{robustness['metrics']['neighbour_overlap']['pca']['mean']:.3f}")
        st.info("Current neural representation did not outperform PCA on neighbour preservation.")
        st.caption(f"Fixed latent architecture: {config['architecture']}")

    if mode == "Existing Player":
        st.subheader("Existing Player Explorer")
        cols = st.columns([4, 1])
        with cols[0]:
            selected_name = st.selectbox("Player", names, index=selected_index, key="existing_player")
        with cols[1]:
            if st.button("Load Wirtz"):
                st.session_state["existing_player"] = names[wirtz_index]
                st.rerun()
        selected = next(row for row in seasons if row["player_name"] == selected_name)
        st.markdown("### PLAYER")
        summary_cols = st.columns(6)
        summary_cols[0].metric("Matches analysed", selected["matches"])
        summary_cols[1].metric("Minutes", f"{selected['minutes']:.1f}")
        for col, key in zip(summary_cols[2:], ["z1_mean", "z2_mean", "z3_mean", "z4_mean"]):
            col.metric(key.replace("_mean", ""), f"{selected[key]:.3f}")
        if selected.get("low_confidence") in (True, "True"):
            st.warning("Fewer than five eligible matches; treat this season embedding as low-confidence.")

        st.subheader("Nearest players")
        nearest = nearest_players(selected, seasons, artifacts["similarity"], artifacts["scaler"]["latent_train_mean"])[:5]
        st.dataframe([{ "Rank": row["rank"], "Player": row["player_name"],
                        "Cosine similarity": row["cosine_similarity"],
                        "Euclidean distance": row["euclidean_distance"]} for row in nearest],
                     use_container_width=True, hide_index=True)

        st.subheader("Role prototype comparison")
        st.caption("This is not a position classification.")
        compared = prototype_comparison(_embedding(selected), artifacts["prototypes"], artifacts["scaler"]["latent_train_mean"])
        if compared:
            closest = compared[0]
            st.success(f"Nearest prototype: {closest['group']} · cosine {closest['cosine_similarity']:.3f} · Euclidean {closest['euclidean_distance']:.3f}")
            st.dataframe([{"Prototype": row["group"], "Cosine similarity": row["cosine_similarity"],
                           "Euclidean distance": row["euclidean_distance"]} for row in compared],
                         use_container_width=True, hide_index=True)
        else:
            st.warning("No role prototypes are available in the saved output.")

        st.subheader("Embedding map")
        figure, _, _ = make_embedding_figure(seasons, selected["player_id"])
        st.pyplot(figure, clear_figure=True)
        st.caption("Visualization only: PCA projects the existing 4-D latent embeddings to two dimensions; it is not used to train the encoder.")
    else:
        st.subheader("Custom Tactical Features")
        st.caption("Enter the same 15 M3 tactical features. Training-range values are shown as guidance; this is a distribution range warning, not AI confidence.")
        preset = st.radio("Initial values", ["Training mean", "Selected existing player's feature mean"], horizontal=True)
        selected_name = st.selectbox("Use this player's feature mean", names, index=wirtz_index,
                                     disabled=preset == "Training mean")
        defaults = build_custom_defaults(artifacts, selected_name if preset != "Training mean" else None)
        with st.form("custom_tactical_profile"):
            values = {}
            left, right = st.columns(2)
            for index, feature in enumerate(artifacts["feature_order"]):
                minimum = float(artifacts["scaler"]["train_min"][index])
                maximum = float(artifacts["scaler"]["train_max"][index])
                default = float(defaults[feature])
                container = left if index % 2 == 0 else right
                with container:
                    values[feature] = st.number_input(feature, value=default, format="%.6f",
                                                      help=f"Training range: {minimum:.4f} to {maximum:.4f}")
            submitted = st.form_submit_button("ENCODE TACTICAL PROFILE")
        if submitted:
            try:
                with warnings.catch_warnings(record=True) as captured:
                    result = __import__("src.models.inference", fromlist=["encode_player_match"]).encode_player_match(values)
                if captured:
                    st.warning("Extra input columns were ignored by the inference API.")
                embedding = result["embedding"]
                st.markdown("### Embedding")
                cols = st.columns(4)
                for col, value, key in zip(cols, embedding, ["z1", "z2", "z3", "z4"]):
                    col.metric(key, f"{value:.4f}")
                if result["out_of_range"]:
                    st.warning("Some inputs are outside the model's training range.")
                    st.write("Out-of-range features:", ", ".join(result["out_of_range_features"]))
                else:
                    st.success("All inputs are within the model's training range.")
                if result["nearest_prototype"]:
                    st.success(f"Nearest prototype: {result['nearest_prototype']} · cosine {result['cosine_similarity']:.3f} · Euclidean {result['prototype_euclidean_distance']:.3f}")
                st.dataframe([{"Prototype": row["group"], "Cosine similarity": row["cosine_similarity"],
                               "Euclidean distance": row["euclidean_distance"]} for row in result["prototype_comparisons"]],
                             use_container_width=True, hide_index=True)
            except (ValueError, TypeError, OverflowError) as exc:
                st.error(f"Could not encode this tactical profile: {exc}")


def main() -> None:
    _render()


if __name__ == "__main__":
    main()
