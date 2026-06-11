KAGGLE_API_TOKEN=${KAGGLE_API_TOKEN} uv run kaggle competitions download -c birdclef-2026 -p input \
    && unzip input/birdclef-2026.zip -d input
