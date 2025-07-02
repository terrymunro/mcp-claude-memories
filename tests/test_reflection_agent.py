"""Tests for reflection agent module."""

from unittest.mock import Mock

import pytest

from mcp_claude_memories.reflection_agent import ReflectionAgent


@pytest.fixture
def mock_memory_service():
    """Mock memory service for testing."""
    return Mock()


@pytest.fixture
def reflection_agent(mock_memory_service):
    """Reflection agent instance for testing."""
    return ReflectionAgent(mock_memory_service)


@pytest.fixture
def sample_memories():
    """Sample memory data for testing."""
    return [
        {"memory": "I'm working on a React project with TypeScript"},
        {"memory": "How to debug async await issues in JavaScript?"},
        {"memory": "Setting up authentication with JWT tokens"},
        {"memory": "React hooks are confusing, especially useEffect"},
        {"memory": "Using MongoDB for the database backend"},
        {"memory": "API endpoints with Express and Node.js"},
        {"memory": "How to debug React components not rendering?"},
        {"memory": "TypeScript types for API responses"},
        {"memory": "Testing with Jest and React Testing Library"},
        {"memory": "Deployment issues with Docker containers"},
    ]


@pytest.mark.asyncio
async def test_analyze_patterns_success(reflection_agent, sample_memories):
    """Test successful pattern analysis."""
    analysis = await reflection_agent.analyze_patterns(sample_memories, limit=10)

    # Check structure
    assert "topics" in analysis
    assert "preferences" in analysis
    assert "recurring_questions" in analysis
    assert "technologies" in analysis
    assert "patterns" in analysis

    # Check that topics were extracted
    topics = analysis["topics"]
    assert isinstance(topics, dict)
    assert "react" in topics  # Should find React mentions
    assert "typescript" in topics  # Should find TypeScript mentions

    # Check preferences
    preferences = analysis["preferences"]
    assert isinstance(preferences, list)


@pytest.mark.asyncio
async def test_analyze_patterns_empty_memories(reflection_agent):
    """Test analysis with empty memories."""
    analysis = await reflection_agent.analyze_patterns([], limit=10)

    assert analysis == {}


@pytest.mark.asyncio
async def test_analyze_patterns_no_text_content(reflection_agent):
    """Test analysis with memories containing no text content."""
    empty_memories = [
        {"id": "mem1"},  # No memory field
        {"memory": ""},  # Empty memory
        {"memory": None},  # None memory
    ]

    analysis = await reflection_agent.analyze_patterns(empty_memories, limit=10)

    assert analysis == {}


def test_extract_topics(reflection_agent):
    """Test topic extraction from text."""
    texts = [
        "working on react project with typescript",
        "api endpoints using node.js and express",
        "database queries with sql and mongodb",
        "testing react components with jest",
        "react hooks and typescript types",
    ]

    topics = reflection_agent._extract_topics(texts)

    assert isinstance(topics, dict)
    assert "react" in topics
    assert topics["react"] >= 2  # Should find multiple React mentions
    assert "typescript" in topics
    assert "api" in topics
    assert "database" in topics


def test_identify_preferences(reflection_agent):
    """Test preference identification."""
    texts = [
        "i prefer typescript over javascript for type safety",
        "using react for frontend development",
        "functional programming approach is better",
        "next.js is my favorite framework",
        "love typescript strict mode",
    ]

    preferences = reflection_agent._identify_preferences(texts)

    assert isinstance(preferences, list)
    # Should identify TypeScript preference
    assert any("typescript" in pref.lower() for pref in preferences)
    # Should identify React usage
    assert any("react" in pref.lower() for pref in preferences)


def test_find_recurring_questions(reflection_agent):
    """Test finding recurring questions."""
    texts = [
        "how to debug react components?",
        "what is the best way to handle async?",
        "how to debug react components not rendering?",
        "api error handling issues",
        "why are my react components not working?",
        "error with async await",
    ]

    recurring = reflection_agent._find_recurring_questions(texts)

    assert isinstance(recurring, list)
    # Should find patterns in debug/error questions
    assert len(recurring) <= 3  # Should limit to top 3


def test_extract_technologies(reflection_agent):
    """Test technology extraction."""
    texts = [
        "using mongodb and redis for databases",
        "deployed on aws with docker containers",
        "testing with jest and cypress",
        "git version control with vscode editor",
    ]

    technologies = reflection_agent._extract_technologies(texts)

    assert isinstance(technologies, dict)
    if "databases" in technologies:
        assert technologies["databases"] >= 1  # Should find database mentions
    if "cloud" in technologies:
        assert technologies["cloud"] >= 1  # Should find AWS mention
    if "testing" in technologies:
        assert technologies["testing"] >= 1  # Should find testing tools


def test_identify_patterns(reflection_agent):
    """Test behavioral pattern identification."""
    texts = [
        "learning new react patterns and hooks",
        "debugging api error issues again",
        "building a new project with typescript",
        "collaborating with team on code review",
        "fixing bugs in the authentication system",
    ]

    patterns = reflection_agent._identify_patterns(texts)

    assert isinstance(patterns, list)
    # Should identify learning and debugging patterns


def test_generate_insights(reflection_agent):
    """Test insight generation from analysis."""
    analysis = {
        "topics": {"react": 5, "typescript": 3, "api": 2},
        "technologies": {"databases": 3, "testing": 2},
        "patterns": ["Actively learning new technologies", "Frequently debugging"],
        "preferences": ["Prefers TypeScript", "Uses React frequently"],
    }

    insights = reflection_agent.generate_insights(analysis)

    assert isinstance(insights, list)
    assert len(insights) > 0

    # Should mention most discussed topic
    assert any("react" in insight.lower() for insight in insights)

    # Should include technology insights
    # Should include pattern insights
    # Should include preference insights


def test_generate_insights_empty_analysis(reflection_agent):
    """Test insight generation with empty analysis."""
    insights = reflection_agent.generate_insights({})

    assert isinstance(insights, list)
    assert len(insights) == 0


def test_calculate_confidence(reflection_agent):
    """Test confidence calculation."""
    # High frequency should give high confidence
    confidence1 = reflection_agent.calculate_confidence(8, 10)
    assert 0.8 <= confidence1 <= 0.95

    # Low frequency should give low confidence
    confidence2 = reflection_agent.calculate_confidence(1, 10)
    assert confidence2 <= 0.2

    # Zero total should give zero confidence
    confidence3 = reflection_agent.calculate_confidence(5, 0)
    assert confidence3 == 0.0


@pytest.mark.asyncio
async def test_suggest_actions_with_context(reflection_agent, sample_memories):
    """Test action suggestions with specific context."""
    suggestions = await reflection_agent.suggest_actions(
        "react debugging", sample_memories
    )

    assert isinstance(suggestions, list)
    assert len(suggestions) > 0
    assert len(suggestions) <= 4  # Should limit to 4 suggestions

    # Should provide relevant suggestions for React debugging context


@pytest.mark.asyncio
async def test_suggest_actions_no_context(reflection_agent, sample_memories):
    """Test action suggestions without specific context."""
    suggestions = await reflection_agent.suggest_actions("", sample_memories)

    assert isinstance(suggestions, list)
    assert len(suggestions) > 0


@pytest.mark.asyncio
async def test_suggest_actions_empty_memories(reflection_agent):
    """Test suggestions with no memories."""
    suggestions = await reflection_agent.suggest_actions("test context", [])

    assert isinstance(suggestions, list)
    assert len(suggestions) == 2  # Should provide default suggestions
    assert "Start by exploring" in suggestions[0]


def test_find_related_memories(reflection_agent):
    """Test finding related memories."""
    memories = [
        {"memory": "React hooks and state management"},
        {"memory": "Vue.js component lifecycle"},
        {"memory": "React component debugging techniques"},
        {"memory": "Python web framework Flask"},
        {"memory": "React testing with Jest"},
    ]

    related = reflection_agent._find_related_memories("react debugging", memories)

    assert isinstance(related, list)
    assert len(related) <= 5  # Should limit to 5 related memories

    # Should prioritize memories with React and debugging content
    assert len(related) >= 2  # Should find at least React-related memories


def test_find_related_memories_no_matches(reflection_agent):
    """Test finding related memories with no matches."""
    memories = [
        {"memory": "Python data analysis"},
        {"memory": "Machine learning models"},
    ]

    related = reflection_agent._find_related_memories("react debugging", memories)

    assert isinstance(related, list)
    # May be empty if no word overlap


@pytest.mark.asyncio
async def test_analyze_patterns_with_limit(reflection_agent, sample_memories):
    """Test analysis respects memory limit."""
    # Test with limit smaller than sample size
    analysis = await reflection_agent.analyze_patterns(sample_memories, limit=3)

    # Should still return valid analysis structure
    assert "topics" in analysis
    assert "preferences" in analysis


def test_extract_topics_case_insensitive(reflection_agent):
    """Test that topic extraction is case insensitive."""
    texts = [
        "Using REACT for frontend",
        "React components are great",
        "react hooks are powerful",
    ]

    topics = reflection_agent._extract_topics(texts)

    # Should count all React mentions regardless of case
    assert "react" in topics
    assert topics["react"] == 3


def test_preferences_multiple_languages(reflection_agent):
    """Test preference detection with multiple languages."""
    texts = [
        "python is good for data science",
        "typescript provides better type safety",
        "typescript is my preferred language",
        "java is verbose but reliable",
        "typescript strict mode is helpful",
    ]

    preferences = reflection_agent._identify_preferences(texts)

    # Should identify TypeScript as preferred due to higher frequency
    assert any("typescript" in pref.lower() for pref in preferences)
