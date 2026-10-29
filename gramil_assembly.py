"""Builds gramil_assembly.step: gramil, a purfling cutter, as one assembly STEP of its 12 parts.

gramil is pzfreo/gramil (its model, in gramil/, under the Open Community License v1: see
gramil/LICENSE). Run with build123d 0.10 and pydantic installed:

    python gramil_assembly.py

The production build (process.prototype False, as gramil's scripts/build_production.py): its
threads are cosmetic, as a supplier's STEP gives them.
"""
from build123d import export_step

from gramil.assembly import build_assembly
from gramil.parameters import PurflingCutterParams

params = PurflingCutterParams()
params = params.model_copy(update={"process": params.process.model_copy(update={"prototype": False})})
export_step(build_assembly(params), "gramil_assembly.step")
