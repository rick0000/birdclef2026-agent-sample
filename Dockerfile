FROM gcr.io/kaggle-gpu-images/python:v168

ARG USER_ID
ARG GROUP_ID
ARG USER_NAME

RUN curl -fsSL https://deb.nodesource.com/setup_22.x | bash - && \
    apt-get update && apt-get install -y nodejs && \
    rm -rf /var/lib/apt/lists/*

RUN npm install -g @anthropic-ai/claude-code

# kaggle-gpu-images ships a `jupyter` user occupying UID 1000.
# Remove it so we can create our own user matching the host UID/GID.
RUN userdel -r jupyter && \
    groupadd -g ${GROUP_ID} ${USER_NAME} && \
    useradd -m -u ${USER_ID} -g ${GROUP_ID} -s /bin/bash ${USER_NAME}

# Install uv
COPY --from=ghcr.io/astral-sh/uv:0.11.5 /uv /uvx /usr/local/bin/

COPY uv.lock pyproject.toml /kaggle/
RUN cd /kaggle && uv sync

USER ${USER_NAME}
WORKDIR /kaggle

CMD ["/bin/bash"]