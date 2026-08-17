#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""pytest 共享配置：把项目根目录加入 sys.path"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
