# Krita integration in ComfyUI
Minimal Krita extension and ComfyUI custom nodes for integrating both UIs together. 

## ⚠️ WIP
This project is in active development. 

## 🔨 Scope of the project
### Krita
- [x] Requires only a running and accessible ComfyUI server
- [x] Adds a settings popup under `settings/ComfyUI...` to set up the ComfyUI URL
- [ ] Dynamically updates the workflow inputs in Krita based on the opened workflow in ComfyUI
- [ ] Allows users to select a list of layers to composite into a single image before sending as workflow input

### ComfyUI
- [x] Exposes the currently opened workflow in the UI to Krita
- [x] Minimizes patching and hijacking of ComfyUI internals to avoid maintenance hell
- [ ] Test brittle code with CI
- [ ] `Save Image (as krita layer)`: sends the generated image back to a specified location in Krita’s layer tree
- [ ] `Load Image (from krita layers)`: composites specific Krita layers and sends them as a single image to ComfyUI
- [ ] `Load Mask (from Krita selection)`: retrieves the active mask selection 
- [ ] `Load Image (from krita document)`: retrieves all the active layers of a document composited together

## 🎲 Why another ComfyUI-Krita extension? 
Existing ComfyUI-Krita extensions tend to do both **too much** and **too little**.

An idiomatic extension:
- Avoids unnecessary dependencies  
- Preserves native features of both Krita and ComfyUI  
- Respects user workflows without intrusive overrides 
