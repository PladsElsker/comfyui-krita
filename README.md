# Krita integration in ComfyUI
Minimal Krita extension and ComfyUI custom nodes for integrating both UIs together.  

## ⚠️ WIP
This project is in active development. 

## 🎲 Why another ComfyUI-Krita extension? 
### ComfyUI is already a UI

If you try to port some features of the UI of ComfyUI to Krita through a Krita extension, a few things can happen:
- `Feature drift` → New UI features in ComfyUI take longer to be ported to the Krita extension
- `Feature masking` → Some useful features like live previews and workflow progress can become inaccessible
- `Dependency hell` → It can be tempting to force users to install unrelated tools and models, even when they don't intend to use them
- Etc.

Instead of reinventing the wheel (and maintaining it), we can use **the best of both worlds**.  

### Minimal. Feature complete. A seemless link. 
Be lazy.  
Existing ComfyUI-Krita extensions tend to do both **too much** and **too little**.  

An idiomatic extension:
- Avoids unnecessary dependencies  
- Preserves native features of both Krita and ComfyUI  
- Respects prior user workflows without intrusive overrides 

## 🔨 Scope of the project
### Krita
- [x] Requires only a running and accessible ComfyUI server
- [x] Adds a settings popup under `settings/ComfyUI...` to set up the ComfyUI URL
- [x] Dynamically updates the workflow inputs and outputs in Krita based on the nodes used in ComfyUI
- [ ] Allows users to select a list of layers to composite into a single image before sending as workflow input

### ComfyUI
- [x] Exposes the currently opened workflow in the UI to Krita
- [x] Minimizes patching and hijacking of ComfyUI internals to avoid maintenance hell
- [ ] Test brittle code with CI
- [ ] `Save Image (as krita layer)`: sends the generated image back to a specified location in Krita’s layer tree
- [ ] `Load Image (from krita layers)`: composites specific Krita layers and sends them as a single image to ComfyUI
- [ ] `Load Mask (from Krita selection)`: retrieves the active mask selection 
- [ ] `Load Image (from krita document)`: retrieves all the active layers of a document composited together
