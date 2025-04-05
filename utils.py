# Copyright 2023 The MediaPipe Authors. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""A module with util functions."""

scoreNames = ["Dog", "Bark", "Bow-wow", "Whimper (dog)"]


def getScoreByNames(result):
    classification = result.classifications[0]
    categories = classification.categories
    scores = dict.fromkeys(scoreNames, 0)

    for cat in categories:
        if cat.category_name in scoreNames:
            scores[cat.category_name] = cat.score

    return scores


def scoreDictToList(scoreDict):
    res = []

    for idx, name in enumerate(scoreNames):
        res[idx] = scoreDict[name]

    return res


def scoreListToDict(scoreList):
    res = {}

    for idx, name in enumerate(scoreNames):
        res[name] = scoreList[idx]

    return res
