# End-to-end test image for the playground: the published Outfitter image
# (node, git, outfitter, bundled pi) plus gh and the other two harness CLIs.
# Build:  docker build -t playground-e2e e2e
# Run:    e2e/test.sh — it mounts your gh token and harness logins.
# Direct: docker run --rm -e ANTHROPIC_API_KEY playground-e2e claude
FROM ghcr.io/ai-outfitter/outfitter:latest

USER root
RUN apt-get update \
  && apt-get install -y --no-install-recommends curl \
  && curl -fsSL https://cli.github.com/packages/githubcli-archive-keyring.gpg \
    -o /usr/share/keyrings/githubcli-archive-keyring.gpg \
  && echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/githubcli-archive-keyring.gpg] https://cli.github.com/packages stable main" \
    > /etc/apt/sources.list.d/github-cli.list \
  && apt-get update \
  && apt-get install -y --no-install-recommends gh \
  && rm -rf /var/lib/apt/lists/* \
  && npm install -g @anthropic-ai/claude-code @openai/codex \
  && npm cache clean --force

COPY --chmod=0755 run.sh /usr/local/bin/playground-e2e
COPY --chmod=0755 demo-entry.sh /usr/local/bin/demo-entry

USER 1000:1000
WORKDIR /workspace
# Default to the credential-free sanity check: a bare `docker run` cannot
# see host logins, so `all` would only skip. e2e/test.sh mounts the
# credentials and is the intended way to run the real legs and the demo.
ENTRYPOINT ["playground-e2e"]
CMD ["check"]
