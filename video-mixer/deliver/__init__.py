# Copyright (C) 2026 rasheedh <rasheedhmech03@gmail.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

"""deliver - a reel, assembled from cues that were each certified on their own.

A cue is scored to its own length and certified against its own picture window.
The reel places the certified cues in reel time and muxes once. The reel never
re-scores, never re-times and never edits a cue's report: it aggregates.
"""
