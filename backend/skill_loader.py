from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import re
import json
from typing import Any, Dict, List, Optional


@dataclass
class SkillDefinition:
    name: str
    path: str
    description: str = ''
    tags: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            'name': self.name,
            'path': self.path,
            'description': self.description,
            'tags': list(self.tags),
            'metadata': dict(self.metadata),
        }


class SkillLoader:
    def __init__(self, root: Optional[str] = None) -> None:
        self.root = Path(root) if root else Path(__file__).resolve().parent.parent / 'skills'
        self.include_project_docs = root is None
        self.project_root = Path(__file__).resolve().parent.parent
        self.project_skill_root = self.project_root / '.claude' / 'skills' / 'skills'
        self.nvidia_skill_root = self.project_root / 'vendor' / 'nvidia-skills' / 'skills'

    @staticmethod
    def _frontmatter(path: Path) -> Dict[str, str]:
        try:
            text = path.read_text(encoding='utf-8')
        except OSError:
            return {}
        if not text.startswith('---'):
            return {}
        match = re.match(r'^---\s*\n(.*?)\n---\s*', text, flags=re.DOTALL)
        if not match:
            return {}
        values: Dict[str, str] = {}
        for line in match.group(1).splitlines():
            key, separator, value = line.partition(':')
            if separator:
                values[key.strip()] = value.strip().strip('"')
        return values

    def _discover_project_docs(self) -> List[SkillDefinition]:
        if not self.project_skill_root.exists():
            return []
        discovered: List[SkillDefinition] = []
        for path in sorted(self.project_skill_root.glob('*/SKILL.md')):
            metadata = self._frontmatter(path)
            name = metadata.get('name') or path.parent.name
            description = metadata.get('description') or f'Skill definition from {path.name}'
            discovered.append(
                SkillDefinition(
                    name=name,
                    path=str(path.relative_to(self.project_root)),
                    description=description,
                    tags=[name.lower()],
                    metadata={
                        'file_type': 'md',
                        'source': 'project_skill',
                        'license': metadata.get('license', ''),
                    },
                )
            )
        return discovered

    def _discover_nvidia_docs(self) -> List[SkillDefinition]:
        catalog_path = self.project_root / 'config' / 'nvidia_skill_catalog.json'
        try:
            catalog = json.loads(catalog_path.read_text(encoding='utf-8'))
        except (OSError, ValueError):
            return []
        selected = {
            item.get('name')
            for item in catalog.get('recommended_for_jarvis', [])
            if isinstance(item, dict) and item.get('name')
        }
        discovered: List[SkillDefinition] = []
        for name in sorted(selected):
            path = self.nvidia_skill_root / name / 'SKILL.md'
            if not path.exists():
                continue
            metadata = self._frontmatter(path)
            discovered.append(
                SkillDefinition(
                    name=f'nvidia:{name}',
                    path=str(path.relative_to(self.project_root)),
                    description=metadata.get('description', f'NVIDIA skill: {name}'),
                    tags=['nvidia', name],
                    metadata={
                        'file_type': 'md',
                        'source': 'nvidia_skill',
                        'agent': next(
                            (
                                item.get('agent')
                                for item in catalog.get('recommended_for_jarvis', [])
                                if isinstance(item, dict) and item.get('name') == name
                            ),
                            'verifier',
                        ),
                        'status': next(
                            (
                                item.get('status')
                                for item in catalog.get('recommended_for_jarvis', [])
                                if isinstance(item, dict) and item.get('name') == name
                            ),
                            'gated',
                        ),
                    },
                )
            )
        return discovered

    def discover(self) -> List[SkillDefinition]:
        if not self.root.exists():
            return []
        skills: List[SkillDefinition] = []
        for path in sorted(self.root.rglob('*')):
            if path.is_dir():
                continue
            suffix = path.suffix.lower()
            if suffix not in {'.py', '.json', '.yaml', '.yml'}:
                continue
            tags = [tag for tag in path.stem.lower().split('_') if tag]
            description = f'Skill from {path.name}'
            skills.append(
                SkillDefinition(
                    name=path.stem,
                    path=str(path.relative_to(self.root.parent)),
                    description=description,
                    tags=tags or ['generic'],
                    metadata={'file_type': suffix.lstrip('.')},
                )
            )
        if not self.include_project_docs:
            return skills
        return skills + self._discover_project_docs() + self._discover_nvidia_docs()

    def load(self) -> List[Dict[str, Any]]:
        return [skill.to_dict() for skill in self.discover()]
