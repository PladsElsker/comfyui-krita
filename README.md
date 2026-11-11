# Krita integration in ComfyUI
Minimal Krita extension and ComfyUI custom nodes for integrating both UIs together.  

## ⚠️ WIP
This project is in active development. 

## 🎲 Why another ComfyUI-Krita extension? 
### ComfyUI is already a UI

If you try to port some features of ComfyUI to Krita through a Krita extension, a few things can happen:
- `Feature drift` → New UI features in ComfyUI take longer to be ported to the Krita extension
- `Feature masking` → Some useful features like live previews and workflow progress can become inaccessible
- `Dependency hell` → It can be tempting to force users to install unrelated tools and models, even when they don't intend to use them
- Etc.

Instead of reinventing the wheel (and maintaining it), we can leverage **the best of both worlds**.  

### Be lazy
Existing ComfyUI-Krita extensions tend to do both **too much** and **too little**.  

An idiomatic extension:
- Avoids unnecessary dependencies  
- Preserves native features of both Krita and ComfyUI  
- Respects prior user workflows and habits by avoiding intrusive overrides 

## 🔨 Scope of the project
### Krita
- [x] Requires only a running and accessible ComfyUI server
- [x] Adds a settings popup under `settings/ComfyUI...` to set up the ComfyUI URL
- [x] Dynamically updates the workflow nodes in Krita based on the nodes used in ComfyUI
- [x] Selects multiple layers in a dedicated thumbnail hierarchy modal without changing the Layers Docker selection

### ComfyUI
- [x] Exposes the currently opened workflow in the UI to Krita
- [x] Minimizes patching and hijacking of ComfyUI internals to avoid maintenance hell
- [x] Brittle frontend dependencies are tested everyday with CI
- [x] Compatibility with nodes 2.0
- [x] `Save Image (as krita layer)` → Sends the generated image back to a specified location in Krita’s layer tree
- [x] `Load Image (from krita layers)` → Composites selected Krita layers, refreshes the node preview when the composition changes, and supplies IMAGE/MASK outputs to ComfyUI
- [ ] `Load Mask (from Krita selection)` → Retrieves the active mask selection 
- [ ] `Load Image (from krita document)` → Retrieves all the active layers of a document composited together

## 🖥️ Tested environments
This extension has been tested and developped with:
- Krita on Windows
- ComfyUI on Ubuntu

It may work on other system configurations, but other configurations won't be tested for practical reasons. 


### Load Image behavior

The Load Image and Save Image edit actions use one shared Krita layer-hierarchy modal. It shows layer thumbnails, supports filtering and hierarchical selection, and leaves the native Layers Docker selection untouched. The Load Image selection is tracked by Krita layer UUIDs; document input events are debounced, and a new snapshot is uploaded only when its canonical RGBA pixel digest differs from the last accepted composition. The ComfyUI preview is refreshed from the uploaded snapshot without requiring a prompt run. A changed snapshot updates the hidden execution metadata so normal ComfyUI graph/cache invalidation and auto-queue behavior can take effect.

ComfyUI node identity is sent as a graph-scoped locator rather than a local numeric node ID, which avoids collisions between nodes inside different subgraph definitions. Snapshot storage revalidates the selection generation after asynchronous hashing and preview-file creation, and evicted snapshots invalidate their corresponding node state.
