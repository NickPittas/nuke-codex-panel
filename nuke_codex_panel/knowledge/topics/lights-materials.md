---
id: "topics/lights-materials"
kind: "topic"
title: "Adding lights, shaders and materials to geometry"
category: "3d-animation-shaders"
summary: "Apply lights, shaders and materials in the node family that the chosen render node understands: Classic shaders/lights with Scene, or New 3D Geo* materials and Nuke/USD lights with GeoScene."
aliases: ["shader", "material", "applymaterial", "geobindmaterial", "basicsurface", "diffuse specular", "directlight pointlight spotlight", "usd lights", "mtlx", "shadows"]
tags: ["3d", "lighting", "material", "shader", "render"]
requires: ["fundamentals/channels-data", "fundamentals/color-spaces"]
related: ["topics/rendering-3d", "topics/texture-projection", "topics/multipass-cg", "topics/cg-backgrounds"]
nodes: ["Diffuse", "Specular", "Emission", "BasicMaterial", "ApplyMaterial", "Light", "DirectLight", "PointLight", "SpotLight", "EnvironmentLight", "BasicSurface", "ReflectiveSurface", "MtlXStandardSurface", "GeoBindMaterial", "GeoEditLight", "ScanlineRender"]
version: "Nuke 17.1 documentation; check installed node generation and licence."
source_ids: ["foundry-17.1", "brinkmann-2e"]
---
# Adding lights, shaders and materials to geometry

## Applicability
Lighting and materials only matter if the render node uses them, so identify the renderer first.
- Classic 3D: Scene -> ScanlineRender/RayRender. Shaders (3D > Shader: Diffuse, Specular, Emission, BasicMaterial and others) sit between the 2D texture and the object's `img` input, or on ApplyMaterial `mat`. Lights: DirectLight, Point, Spotlight, Environment, or Light (direct/point/spot, can read FBX lights).
- New 3D System: GeoScene -> ScanlineRender (`ScanlineRender2`) or GeoRender (Hydra). Shaders: BasicSurface, ReflectiveSurface, MtlXStandardSurface, ConstantShader, FillShader, WireframeShader, MergeLayerShader, Project3DShader; PreviewSurface is Beta in the docs. Bind with GeoBindMaterial or a primitive's `mat` input.
Foundry has no direct Classic Phong in New 3D; BasicSurface or MtlXStandardSurface approximate it. Do not wire Classic shaders to Geo* geometry.

## Workflow
Classic:
1. Texture -> shader(s) -> geometry `img`, or geometry -> ApplyMaterial with the shader on `mat`. ApplyMaterial applies to all incoming objects by default, or filter by object name; connecting it to MergeGeo overrides materials on the merged inputs.
2. Add lights to the Scene. Use Normals to control diffuse/specular response if needed. Enable `cast shadows` on a light and cast/receive shadow on the objects (Scene node can override); a receiving material needs a shader.
3. Combine shaders by chaining unlabeled inputs; Foundry notes some material effects show only in the 2D render, not in the 3D view.

New 3D:
1. Choose Nuke lights (SpotLight, DirectLight, PointLight, EnvironmentLight, converted to USD on injection) or USD lights (GeoDiskLight, GeoDistantLight, GeoDomeLight, GeoSphereLight; GeoEditLight edits imported light prims). Nuke lights joined by GeoScene appear as `{nodename}_Inject` unless a prim path is set.
2. Bind a material with GeoBindMaterial; connect to GeoScene to override materials on all merged geometry.
3. In ScanlineRender, Lighting Enable `auto` lights only when lights exist; `on` renders black without emissive; `off` is constant shading. Material Families default `slr mtlx`; if a material provides no matching family the binding fails and the object is not rendered. Binding Mode and Side Visibility can also hide a material.

## Verify
- In 2D (not just the 3D view) check lit side, falloff, specular position and shadows; change the light direction to confirm it responds.
- Isolate a surface with constant color/emissive to separate shading from texture.
- Compare against plate lighting cues; matching direction/color/shadow is a compositing decision (Brinkmann, Ch. 2 "Light and Shadow"; Ch. 14 "Working with CG Elements").

## Pitfalls
- A texture connected to Classic `img` without a shader may not respond to lights as expected; Foundry's tutorial states shaders on `img` are required for correct lighting.
- Classic ScanlineRender does not support point-light shadows (Light node doc); use direct or spot lights for shadows there, or check the other renderers' docs.
- Re-render versus adjust in 2D: big lighting direction changes usually need a re-render; color balance changes often can be done in comp (Brinkmann Ch. 14).
- Color pipeline matters: material and texture values interpret as the working space defines (see fundamentals/color-spaces).
- Reflection/refraction and AO exist on different nodes per generation; New 3D folds AO into ScanlineRender Integrator Occlusion mode.

## Sources
- Foundry 17.1: https://learn.foundry.com/nuke/17.1/content/comp_environment/3d_compositing/object_material_properties.html
- https://learn.foundry.com/nuke/17.1/content/comp_environment/3d_compositing/casting_shadows.html
- https://learn.foundry.com/nuke/17.1/content/reference_guide/3d_nodes/light.html
- https://learn.foundry.com/nuke/17.1/content/comp_environment/usd-3d-comp/light-scenes.html
- https://learn.foundry.com/nuke/17.1/content/comp_environment/usd-3d-comp/materials-shaders.html
- https://learn.foundry.com/nuke/17.1/content/comp_environment/usd-3d-comp/shading-geometry.html
- https://learn.foundry.com/nuke/17.1/content/reference_guide/3dnew_nodes/scanlinerender.html
- https://learn.foundry.com/nuke/17.1/content/comp_environment/usd-3d-comp/nodes_classic_to_new.html
- Brinkmann 2e Ch. 2 "Light and Shadow"; Ch. 14 "Working with CG Elements".
