# Running Straightedge in a container

The reason to containerise is the **agent lane**. `agent-render` executes
Python that a model wrote; `agent/safety.py` filters it, but an AST allowlist is
defence in depth, not a sandbox. Run that lane isolated whenever the prompt or
the model is not fully trusted.

```bash
docker build -t straightedge-render -f docker/Dockerfile .
```

## Isolate the agent lane

`--network=none` cuts the container off from the network; mounting only an output
directory keeps it off the host filesystem. Generated code that escapes the
checks then has nowhere to go.

```bash
mkdir -p out
docker run --rm --network=none -v "$PWD/out:/out" \
  -e OPENAI_API_KEY="$OPENAI_API_KEY" \
  straightedge-render agent-render "Show why the focal-distance sum of an ellipse is constant" \
  --language en --output-dir /out
```

The model call needs the network, so a fully air-gapped run is not possible for
the agent lane — do the planning where the key lives and hand the reviewed scene
to a `--network=none` container to *render*, or accept that the container reaches
only the model endpoint. Either way the untrusted execution is contained.

## The deterministic lanes need none of this

`render`, `--template`, and the figure lane (`render_diagram`) do not execute
model output. They run on the host, or in the container without `--network`
restrictions:

```bash
docker run --rm -v "$PWD/out:/out" straightedge-render \
  render --template conic/ellipse_foci --output-dir /out --qc
```
