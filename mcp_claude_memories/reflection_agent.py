"""Reflection agent for analyzing conversation patterns and generating insights."""

import logging
import re
from collections import Counter, defaultdict

logger = logging.getLogger(__name__)


class ReflectionAgent:
    """Analyzes conversation patterns and generates insights."""

    def __init__(self, memory_service):
        """Initialize reflection agent with memory service."""
        self.memory_service = memory_service

    async def analyze_patterns(self, memories: list[dict], limit: int = 50) -> dict:
        """Analyze conversation memories for patterns.

        Args:
            memories: List of memory dictionaries from Mem0
            limit: Maximum number of memories to analyze

        Returns:
            Dictionary with analysis results
        """
        if not memories:
            return {}

        # Extract text content from memories
        texts = []
        for memory in memories[:limit]:
            content = memory.get("memory", "")
            if content:
                texts.append(content.lower())

        if not texts:
            return {}

        analysis = {
            "topics": self._extract_topics(texts),
            "preferences": self._identify_preferences(texts),
            "recurring_questions": self._find_recurring_questions(texts),
            "technologies": self._extract_technologies(texts),
            "patterns": self._identify_patterns(texts),
        }

        logger.info(
            f"Analyzed {len(texts)} memories, found {len(analysis['topics'])} topics"
        )
        return analysis

    def _extract_topics(self, texts: list[str]) -> dict[str, int]:
        """Extract frequently discussed topics from texts."""
        # Common technical keywords and phrases
        topic_patterns = {
            "react": r"\breact\b",
            "typescript": r"\btypescript\b|\bts\b",
            "javascript": r"\bjavascript\b|\bjs\b",
            "python": r"\bpython\b",
            "api": r"\bapi\b|\bendpoint\b|\brest\b",
            "database": r"\bdatabase\b|\bdb\b|\bsql\b|\bmongo\b",
            "authentication": r"\bauth\b|\blogin\b|\btoken\b|\bjwt\b",
            "frontend": r"\bfrontend\b|\bui\b|\bcomponent\b",
            "backend": r"\bbackend\b|\bserver\b|\bnode\b",
            "testing": r"\btest\b|\btesting\b|\bunit test\b",
            "deployment": r"\bdeploy\b|\bdeployment\b|\bproduction\b",
            "debugging": r"\bbug\b|\berror\b|\bdebug\b|\bfix\b",
            "performance": r"\bperformance\b|\boptimiz\b|\bspeed\b",
            "css": r"\bcss\b|\bstyl\b|\bsass\b|\bless\b",
            "docker": r"\bdocker\b|\bcontainer\b",
            "git": r"\bgit\b|\bversion control\b|\bcommit\b",
            "async": r"\basync\b|\bawait\b|\bpromise\b",
        }

        topic_counts = Counter()

        combined_text = " ".join(texts)

        for topic, pattern in topic_patterns.items():
            matches = re.findall(pattern, combined_text, re.IGNORECASE)
            if matches:
                topic_counts[topic] = len(matches)

        # Return top topics
        return dict(topic_counts.most_common(10))

    def _identify_preferences(self, texts: list[str]) -> list[str]:
        """Identify user preferences from conversation patterns."""
        preferences = []
        combined_text = " ".join(texts)

        # Language preferences
        language_counts = Counter()
        languages = ["typescript", "javascript", "python", "java", "go", "rust", "c++"]

        for lang in languages:
            count = len(re.findall(rf"\b{lang}\b", combined_text, re.IGNORECASE))
            if count > 0:
                language_counts[lang] = count

        if language_counts:
            top_lang = language_counts.most_common(1)[0][0]
            preferences.append(f"Prefers {top_lang.title()} programming")

        # Framework preferences
        frameworks = {
            "react": r"\breact\b",
            "vue": r"\bvue\b",
            "angular": r"\bangular\b",
            "next.js": r"\bnext\.?js\b",
            "express": r"\bexpress\b",
            "fastapi": r"\bfastapi\b",
            "django": r"\bdjango\b",
        }

        framework_counts = Counter()
        for fw, pattern in frameworks.items():
            count = len(re.findall(pattern, combined_text, re.IGNORECASE))
            if count > 0:
                framework_counts[fw] = count

        if framework_counts:
            top_fw = framework_counts.most_common(1)[0][0]
            preferences.append(f"Frequently uses {top_fw}")

        # Style preferences
        if re.search(r"\bfunctional\b.*\bprogramming\b", combined_text, re.IGNORECASE):
            preferences.append("Shows interest in functional programming")

        if re.search(
            r"\btype\b.*\bsafety\b|\bstrong.*typing\b", combined_text, re.IGNORECASE
        ):
            preferences.append("Values type safety")

        if re.search(r"\btest\b.*\bdriven\b|\btdd\b", combined_text, re.IGNORECASE):
            preferences.append("Interested in test-driven development")

        return preferences[:5]  # Return top 5 preferences

    def _find_recurring_questions(self, texts: list[str]) -> list[str]:
        """Find questions or problems that appear multiple times."""
        # Look for common question patterns
        question_patterns = [
            r"how to.*\?",
            r"what.*\?",
            r"why.*\?",
            r"when.*\?",
            r"where.*\?",
            r"error.*",
            r"issue.*",
            r"problem.*",
            r"not working.*",
            r"fails.*",
            r"broken.*",
        ]

        questions = []
        combined_text = " ".join(texts)

        for pattern in question_patterns:
            matches = re.findall(pattern, combined_text, re.IGNORECASE)
            questions.extend(matches)

        # Count occurrences
        question_counts = Counter(questions)

        # Return questions that appear more than once
        recurring = []
        for question, count in question_counts.items():
            if count > 1 and len(question.strip()) > 10:
                recurring.append(f"{question.strip()[:50]}... (asked {count} times)")

        return recurring[:3]  # Return top 3 recurring questions

    def _extract_technologies(self, texts: list[str]) -> dict[str, int]:
        """Extract technology stack information."""
        tech_patterns = {
            "databases": [r"\bmongodb\b", r"\bpostgres\b", r"\bmysql\b", r"\bredis\b"],
            "cloud": [
                r"\baws\b",
                r"\bazure\b",
                r"\bgcp\b",
                r"\bvercel\b",
                r"\bnetlify\b",
            ],
            "tools": [r"\bdocker\b", r"\bkubernetes\b", r"\bgit\b", r"\bvscode\b"],
            "testing": [r"\bjest\b", r"\bpytest\b", r"\bcypress\b", r"\bmocha\b"],
        }

        tech_usage = defaultdict(int)
        combined_text = " ".join(texts)

        for category, patterns in tech_patterns.items():
            for pattern in patterns:
                matches = len(re.findall(pattern, combined_text, re.IGNORECASE))
                if matches > 0:
                    tech_usage[category] += matches

        return dict(tech_usage)

    def _identify_patterns(self, texts: list[str]) -> list[str]:
        """Identify behavioral and learning patterns."""
        patterns = []
        combined_text = " ".join(texts)

        # Learning patterns
        if re.search(
            r"\blearn\b.*\bnew\b|\bnew\b.*\blearn\b", combined_text, re.IGNORECASE
        ):
            patterns.append("Actively learning new technologies")

        # Problem-solving patterns
        debugging_words = len(
            re.findall(
                r"\bdebug\b|\bfix\b|\berror\b|\bissue\b", combined_text, re.IGNORECASE
            )
        )
        total_words = len(combined_text.split())

        if debugging_words / total_words > 0.1:
            patterns.append("Frequently works on debugging and problem-solving")

        # Project patterns
        if re.search(
            r"\bproject\b.*\bbuilding\b|\bbuilding\b.*\bproject\b",
            combined_text,
            re.IGNORECASE,
        ):
            patterns.append("Engaged in building projects")

        # Collaboration patterns
        if re.search(
            r"\bteam\b|\bcollaborate\b|\bpair programming\b",
            combined_text,
            re.IGNORECASE,
        ):
            patterns.append("Values collaboration and teamwork")

        return patterns

    def generate_insights(self, analysis: dict) -> list[str]:
        """Generate human-readable insights from analysis.

        Args:
            analysis: Analysis results from analyze_patterns

        Returns:
            List of insight strings
        """
        insights = []

        # Topic insights
        topics = analysis.get("topics", {})
        if topics:
            top_topic = max(topics.items(), key=lambda x: x[1])
            insights.append(
                f"Most discussed topic: {top_topic[0]} ({top_topic[1]} mentions)"
            )

        # Technology insights
        technologies = analysis.get("technologies", {})
        if technologies:
            for category, count in technologies.items():
                if count > 2:
                    insights.append(
                        f"Actively using {category} tools (mentioned {count} times)"
                    )

        # Pattern insights
        patterns = analysis.get("patterns", [])
        for pattern in patterns:
            insights.append(pattern)

        # Preference insights
        preferences = analysis.get("preferences", [])
        for pref in preferences[:2]:  # Top 2 preferences
            insights.append(pref)

        return insights

    def calculate_confidence(self, pattern_count: int, total_memories: int) -> float:
        """Calculate confidence score for insights.

        Args:
            pattern_count: Number of times pattern was observed
            total_memories: Total number of memories analyzed

        Returns:
            Confidence score between 0 and 1
        """
        if total_memories == 0:
            return 0.0

        # Simple confidence calculation based on frequency
        frequency = pattern_count / total_memories

        # Cap confidence at 0.95 to account for uncertainty
        return min(frequency * 2, 0.95)

    async def suggest_actions(
        self, context: str, user_memories: list[dict]
    ) -> list[str]:
        """Generate contextual suggestions based on memories and current context.

        Args:
            context: Current conversation context
            user_memories: List of user's memories

        Returns:
            List of suggested actions
        """
        suggestions = []

        if not user_memories:
            return [
                "Start by exploring your area of interest",
                "Ask questions about technologies you want to learn",
            ]

        # Analyze recent patterns
        analysis = await self.analyze_patterns(user_memories, 20)

        # Context-based suggestions
        if context:
            context_lower = context.lower()

            # Find related memories
            related_memories = self._find_related_memories(context_lower, user_memories)

            if related_memories:
                suggestions.append(
                    f"Based on previous discussions about {context}, consider reviewing the solution we used before"
                )

            # Technology-specific suggestions
            if "react" in context_lower and "react" in analysis.get("topics", {}):
                suggestions.append(
                    "Continue building on your React knowledge - perhaps explore advanced patterns or state management"
                )

            if "error" in context_lower or "debug" in context_lower:
                suggestions.append(
                    "Try systematic debugging: check logs, isolate the problem, and test individual components"
                )

        # General suggestions based on patterns
        topics = analysis.get("topics", {})
        if topics:
            top_topic = max(topics.items(), key=lambda x: x[1])[0]
            suggestions.append(
                f"Continue exploring {top_topic} - you've been actively working with it"
            )

        preferences = analysis.get("preferences", [])
        if preferences:
            suggestions.append(
                f"Given your interests, you might enjoy diving deeper into: {preferences[0].lower()}"
            )

        # Learning suggestions
        if (
            "learn"
            in " ".join([m.get("memory", "") for m in user_memories[-5:]]).lower()
        ):
            suggestions.append(
                "Consider building a small project to practice what you've learned"
            )

        # Default suggestions if none generated
        if not suggestions:
            suggestions = [
                "Continue with your current project",
                "Try implementing a new feature you've been thinking about",
                "Review and refactor some recent code",
            ]

        return suggestions[:4]  # Return top 4 suggestions

    def _find_related_memories(self, context: str, memories: list[dict]) -> list[dict]:
        """Find memories related to current context.

        Args:
            context: Current context string (lowercased)
            memories: List of memory dictionaries

        Returns:
            List of related memories
        """
        related = []
        context_words = set(context.split())

        for memory in memories:
            memory_content = memory.get("memory", "").lower()
            memory_words = set(memory_content.split())

            # Calculate word overlap
            overlap = len(context_words.intersection(memory_words))

            if overlap > 0:
                related.append(memory)

        return related[:5]  # Return top 5 related memories
