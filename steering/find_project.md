---
inclusion: auto
name: find_project
description: 当需要查找不在工作区的项目时触发。触发词：找项目, 项目在哪, 不在工作区, 加载项目, 仓库路径, 打开项目
---
<!------------------------------------------------------------------------------------
   Add rules to this file or a short description and have Kiro refine them for you.
   
   Learn about inclusion modes: https://kiro.dev/docs/steering/#inclusion-modes
-------------------------------------------------------------------------------------> 
1. 需要通过`switch-workspace`技能动态加载项目到当前工作区。
2. 禁止使用mcp、shell直接读取、编辑代码。禁止通过mcp 读取代码，请通过readCode工具分析读取代码，如果无法读取请确认项目已经加入到工作区，并等待加载完成
