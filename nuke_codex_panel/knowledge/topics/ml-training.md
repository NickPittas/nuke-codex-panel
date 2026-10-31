---
id: "topics/ml-training"
kind: "topic"
title: "Train and export machine-learning models (CopyCat, BigCat, CatFileCreator)"
category: "machine-learning"
summary: "Set up CopyCat or BigCat training and CatFileCreator .cat export from Python with the documented knobs, start training deliberately, read back .cat/.png outputs and attach an Inference node. Training is long, GPU-bound and licence-gated."
aliases: ["CopyCat", "BigCat", "train a model", "machine learning training", "CatFileCreator", ".cat file", "TorchScript to cat", "Inference node", "startTraining"]
tags: ["copycat", "bigcat", "catfilecreator", "inference", "training", "cat", "python"]
requires: ["fundamentals/channels-data"]
related: ["topics/node-graphs"]
nodes: ["CopyCat", "BigCat", "CatFileCreator", "Inference"]
version: "Nuke 17.1v1 installed docs (static, not runtime-verified). BigCat needs NukeX/Studio; headless training needs a NukeX licence. Check licence, GPU and node classes first."
source_ids: ["foundry-17.1"]
---
# Train and export machine-learning models (CopyCat, BigCat, CatFileCreator)

## Applicability
Use when the user asks for a trained model (cleanup, matte, deblur learned from example frames), or to wrap a TorchScript `.pt` as a `.cat`. CopyCat suits one shot or similar shots; BigCat targets hundreds or thousands of pairs. If a preset suffices, use Upscale or Deblur (ordinary knob nodes, no training). Training takes minutes to hours: start it only when explicitly asked, never as a side effect of building a graph.

## Workflow
### CopyCat / BigCat: prepare and start
Inputs: `Input` (before) and `Ground Truth` (after) must be the same format; optional `Preview` shows a frame outside the data set. Read `cc.input(i)` after connecting; docs list Input, Ground Truth, Preview in that order.
```python
import nuke, os
cc = nuke.createNode('CopyCat', '', False)       # BigCat uses the same knob names
cc.setInput(0, before); cc.setInput(1, truth)
d = '/path/to/train_dir'; os.makedirs(d, exist_ok=True)
cc['dataDirectory'].setValue(d)                  # required: .cat and contact-sheet .png are written here
cc['epochs'].setValue(10000)                     # default 10000; only change on request
cc['useGPUIfAvailable'].setValue(True)
cc['initialWeights'].setValue('None')            # or 'Checkpoint' + checkpointFile; docs also list Deblur, Upscale, Human Matting
print(cc['gpuName'].value(), cc['trainingInfo'].value())   # GPU and read-only channels/steps summary
```
Other documented knobs: `modelSize`, `batchSizeType`, `cropSize` (default 256), `checkpointInterval` (1000), `imageInterval` (100), `useMultiResolutionTraining`. BigCat adds `verifyInputs`, colour/transform augmentation (`useRGBColorAugmentation`, `useTransformAugmentation`) and loss weights (`l1Weight`, `l2Weight`, `perceptualLossModel`).
```python
def press(n, k):
    kn = n[k]
    if not hasattr(kn, 'execute'): raise RuntimeError(k + ' not scriptable; ask user to click it')
    kn.execute()
press(cc, 'startTraining')    # or resumeTraining from a checkpoint in dataDirectory
```
The docs describe `startTraining` only as a click (Progress tab shows Step/Loss); whether `execute()` blocks the GUI is not documented, so report that training began rather than assuming completion. The documented non-interactive route is the command line: `Nuke --nukex -i -F 1 -X CopyCat1 --gpu script.nk` (`-X` executes the named node; omit `--gpu` and it runs on CPU). A Python `nuke.execute('CopyCat1', 1, 1, 1)` equivalent is inferred from `-X`, not documented.

### Read back and apply
```python
files = sorted(f for f in os.listdir(d) if f.endswith(('.cat', '.png')))
cats = [f for f in files if f.endswith('.cat')]
before_inf = set(nuke.allNodes('Inference'))
press(cc, 'createInference')                      # adds an Inference node whose Model File references the .cat
inf = (set(nuke.allNodes('Inference')) - before_inf).pop()
print(inf['modelFile'].value())
```
Standalone Inference: `modelFile`, `channelsIn`, `channelsOut`, `inferencePrecision`, `useGPUIfAvailable`; connect it to the source and view a frame. Checkpoint `.cat` files (every `checkpointInterval` steps) can be applied before training finishes.

### CatFileCreator: `.pt` to `.cat`
```python
cf = nuke.createNode('CatFileCreator', '', False)
cf['torchScriptFileKnob'].setValue('/path/model.pt')
cf['catFileKnob'].setValue('/path/model.cat')
cf['channelsInKnob'].setValue('rgba.red,rgba.green,rgba.blue')    # comma list matching the model
cf['channelsOuKnob'].setValue('rgba.red,rgba.green,rgba.blue')    # knob name is spelled channelsOuKnob
cf['modelIdKnob'].setValue('my_model')                            # optional
press(cf, 'createCatFileKnob')                                    # creates the .cat and an Inference node
assert os.path.getsize('/path/model.cat') > 0
```
Channel names and the `.pt` interface must match the model; user knobs exposed on Inference need a `.pt` with the documented variables (Foundry .cat File Creation Guide).

## Verify
`.cat` exists and is non-empty in `dataDirectory`; contact sheets show the Preview moving toward Ground Truth; the Inference `modelFile` points at the file; view the Inference output on a frame not in the data set.

## Pitfalls
- Input and Ground Truth sizes differ, or the data directory is empty or unset: training fails or writes nowhere.
- No usable GPU means CPU training, far slower; read `gpuName`.
- Do not restart training over an existing `dataDirectory` run without asking; use `resumeTraining`.
- Docs are static: confirm node classes and licences in the session.

## Sources
- /opt/Nuke17.1v1/Documentation/html/content/reference_guide/air_nodes/{copycat,bigcat,catfilecreator,inference}.html
- /opt/Nuke17.1v1/Documentation/html/content/comp_environment/air_tools/{cc-train,cc-headless-train,cc-apply,cfc-intro}.html
