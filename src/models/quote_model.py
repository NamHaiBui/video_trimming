from typing import List, Dict, Any, Optional
from datetime import datetime
import json
import csv
from pathlib import Path
from urllib.parse import urlparse


class WordTimestamp:
    """Model for individual word timestamps"""
    
    def __init__(self, word: str, start_time: float, end_time: float):
        self.word = self._validate_word(word)
        self.start_time = self._validate_time(start_time, "start_time")
        self.end_time = self._validate_time(end_time, "end_time")
        self._validate_time_order()
    
    def _validate_word(self, word: str) -> str:
        if not isinstance(word, str):
            raise ValueError('Word must be a string')
        return word
    
    def _validate_time(self, time_val: float, field_name: str) -> float:
        if not isinstance(time_val, (int, float)):
            raise ValueError(f'{field_name} must be a number')
        if time_val < 0:
            raise ValueError(f'{field_name} must be non-negative')
        return float(time_val)
    
    def _validate_time_order(self):
        if self.end_time < self.start_time:
            raise ValueError('End time must be after start time')
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'word': self.word,
            'start_time': self.start_time,
            'end_time': self.end_time
        }


class TimeRange:
    """Model for time ranges"""
    
    def __init__(self, start_time: float, end_time: float):
        self.start_time = self._validate_time(start_time, "start_time")
        self.end_time = self._validate_time(end_time, "end_time")
        self._validate_time_order()
    
    def _validate_time(self, time_val: float, field_name: str) -> float:
        if not isinstance(time_val, (int, float)):
            raise ValueError(f'{field_name} must be a number')
        if time_val < 0:
            raise ValueError(f'{field_name} must be non-negative')
        return float(time_val)
    
    def _validate_time_order(self):
        if self.end_time < self.start_time:
            raise ValueError('End time must be after start time')
    
    @property
    def duration(self) -> float:
        """Calculate duration in seconds"""
        return self.end_time - self.start_time
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'start_time': self.start_time,
            'end_time': self.end_time
        }


class Quote:
    """Main model for podcast quotes"""
    
    def __init__(self, **kwargs):
        # Handle field aliasing
        self.podcast_title = kwargs.get('podcast_title', '')
        self.episode_title_quote_rank = kwargs.get('episode_title#quote_rank', '')
        self.context = kwargs.get('context', '')
        self.context_length = float(kwargs.get('context_length', 0))
        self.episode_title = kwargs.get('episode_title', '')
        self.generated_quote_uuid = kwargs.get('generated_quote_uuid', '')
        self.genre = kwargs.get('genre', '')
        self.quote = kwargs.get('quote', '')
        self.quote_length = float(kwargs.get('quote_length', 0))
        self.quote_rank = int(kwargs.get('quote_rank', 1))
        self.sentiment = kwargs.get('sentiment', '')
        self.short_description = kwargs.get('Short_description', '')
        self.source_transcript_id = kwargs.get('source_transcript_id', '')
        self.speaker_label = kwargs.get('speaker_label', '')
        self.speaker_name = kwargs.get('speaker_name', '')
        self.topic = kwargs.get('topic', '')
        
        # Parse complex fields
        self.processing_timestamp_utc = self._parse_datetime(kwargs.get('processing_timestamp_utc'))
        self.quote_audio_url = self._validate_url(kwargs.get('quote_audio_url', ''))
        
        # Parse JSON fields
        self.absolute_context_word_timestamps = self._parse_word_timestamps(
            kwargs.get('absolute_context_word_timestamps', '[]')
        )
        self.absolute_quote_word_timestamps = self._parse_word_timestamps(
            kwargs.get('absolute_quote_word_timestamps', '[]')
        )
        self.transcript_level_context_word_timestamps = self._parse_word_timestamps(
            kwargs.get('transcript_level_context_word_timestamps', '[]')
        )
        self.transcript_level_quote_word_timestamps = self._parse_word_timestamps(
            kwargs.get('transcript_level_quote_word_timestamps', '[]')
        )
        self.context_timestamps = self._parse_time_range(kwargs.get('context_timestamps', '{}'))
        self.quote_timestamps = self._parse_time_range(kwargs.get('quote_timestamps', '{}'))
        
        # Validate
        self._validate()
    
    def _validate_url(self, url: str) -> str:
        if not url:
            raise ValueError('URL cannot be empty')
        try:
            result = urlparse(url)
            if not all([result.scheme, result.netloc]):
                raise ValueError('Invalid URL format')
        except Exception:
            raise ValueError('Invalid URL format')
        return url
    
    def _parse_datetime(self, value: Optional[str]) -> datetime:
        if isinstance(value, datetime):
            return value
        if isinstance(value, str):
            # Handle ISO format with Z suffix
            if value.endswith('Z'):
                value = value.replace('Z', '+00:00')
            return datetime.fromisoformat(value)
        if value is None:
            return datetime.now()
        raise ValueError('Invalid datetime format')
    
    def _parse_word_timestamps(self, value) -> List[WordTimestamp]:
        if isinstance(value, list):
            return value
        if isinstance(value, str):
            try:
                data = json.loads(value)
                return [WordTimestamp(
                    word=item['M']['word']['S'],
                    start_time=float(item['M']['start_time']['N']),
                    end_time=float(item['M']['end_time']['N'])
                ) for item in data]
            except (json.JSONDecodeError, KeyError, ValueError) as e:
                raise ValueError(f'Invalid word timestamps format: {e}')
        return []
    
    def _parse_time_range(self, value) -> TimeRange:
        if isinstance(value, TimeRange):
            return value
        if isinstance(value, str):
            try:
                data = json.loads(value)
                return TimeRange(
                    start_time=float(data['start_time']['N']),
                    end_time=float(data['end_time']['N'])
                )
            except (json.JSONDecodeError, KeyError, ValueError) as e:
                raise ValueError(f'Invalid time range format: {e}')
        if isinstance(value, dict):
            return TimeRange(
                start_time=float(value.get('start_time', 0)),
                end_time=float(value.get('end_time', 0))
            )
        return TimeRange(0, 0)
    
    def _validate(self):
        if self.quote_rank < 1:
            raise ValueError('Quote rank must be positive')
        if not self.podcast_title:
            raise ValueError('Podcast title cannot be empty')
        if not self.quote:
            raise ValueError('Quote cannot be empty')
    
    @property
    def quote_duration(self) -> float:
        """Get quote duration in seconds"""
        return self.quote_timestamps.duration
    
    @property
    def context_duration(self) -> float:
        """Get context duration in seconds"""
        return self.context_timestamps.duration
    
    @property
    def words_per_minute(self) -> float:
        """Calculate speaking rate in words per minute"""
        word_count = len(self.quote.split())
        duration_minutes = self.quote_duration / 60
        return word_count / duration_minutes if duration_minutes > 0 else 0
    
    def get_episode_id(self) -> str:
        """Extract episode ID from episode_title_quote_rank"""
        return self.episode_title_quote_rank.split('#')[0] if '#' in self.episode_title_quote_rank else ''
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for easy serialization"""
        return {
            'podcast_title': self.podcast_title,
            'episode_title#quote_rank': self.episode_title_quote_rank,
            'absolute_context_word_timestamps': [wt.to_dict() for wt in self.absolute_context_word_timestamps],
            'absolute_quote_word_timestamps': [wt.to_dict() for wt in self.absolute_quote_word_timestamps],
            'context': self.context,
            'context_length': self.context_length,
            'context_timestamps': self.context_timestamps.to_dict(),
            'episode_title': self.episode_title,
            'generated_quote_uuid': self.generated_quote_uuid,
            'genre': self.genre,
            'processing_timestamp_utc': self.processing_timestamp_utc.isoformat(),
            'quote': self.quote,
            'quote_audio_url': self.quote_audio_url,
            'quote_length': self.quote_length,
            'quote_rank': self.quote_rank,
            'quote_timestamps': self.quote_timestamps.to_dict(),
            'sentiment': self.sentiment,
            'Short_description': self.short_description,
            'source_transcript_id': self.source_transcript_id,
            'speaker_label': self.speaker_label,
            'speaker_name': self.speaker_name,
            'topic': self.topic,
            'transcript_level_context_word_timestamps': [wt.to_dict() for wt in self.transcript_level_context_word_timestamps],
            'transcript_level_quote_word_timestamps': [wt.to_dict() for wt in self.transcript_level_quote_word_timestamps]
        }


class QuoteProcessor:
    """Utility class for processing quote data"""
    
    @staticmethod
    def load_from_csv(file_path: Path) -> List[Quote]:
        """Load quotes from CSV file"""
        quotes = []
        with open(file_path, 'r', encoding='utf-8') as file:
            reader = csv.DictReader(file)
            for row_num, row in enumerate(reader, 1):
                try:
                    quote = Quote(**row)
                    quotes.append(quote)
                except Exception as e:
                    print(f"Error processing row {row_num}: {e}")
                    continue
        return quotes
    
    @staticmethod
    def filter_by_topic(quotes: List[Quote], topic: str) -> List[Quote]:
        """Filter quotes by topic"""
        return [q for q in quotes if q.topic.lower() == topic.lower()]
    
    @staticmethod
    def filter_by_speaker(quotes: List[Quote], speaker: str) -> List[Quote]:
        """Filter quotes by speaker name"""
        return [q for q in quotes if q.speaker_name.lower() == speaker.lower()]
    
    @staticmethod
    def filter_by_sentiment(quotes: List[Quote], sentiment: str) -> List[Quote]:
        """Filter quotes by sentiment"""
        return [q for q in quotes if q.sentiment.lower() == sentiment.lower()]
    
    @staticmethod
    def filter_by_duration(quotes: List[Quote], min_duration: Optional[float] = None, max_duration: Optional[float] = None) -> List[Quote]:
        """Filter quotes by duration range"""
        filtered = quotes
        if min_duration is not None:
            filtered = [q for q in filtered if q.quote_duration >= min_duration]
        if max_duration is not None:
            filtered = [q for q in filtered if q.quote_duration <= max_duration]
        return filtered
    
    @staticmethod
    def get_top_quotes(quotes: List[Quote], limit: int = 10) -> List[Quote]:
        """Get top quotes by rank"""
        return sorted(quotes, key=lambda x: x.quote_rank)[:limit]
    
    @staticmethod
    def group_by_episode(quotes: List[Quote]) -> Dict[str, List[Quote]]:
        """Group quotes by episode"""
        episodes = {}
        for quote in quotes:
            episode_id = quote.get_episode_id()
            if episode_id not in episodes:
                episodes[episode_id] = []
            episodes[episode_id].append(quote)
        return episodes
    
    @staticmethod
    def get_statistics(quotes: List[Quote]) -> Dict[str, Any]:
        """Get basic statistics about the quotes"""
        if not quotes:
            return {}
        
        durations = [q.quote_duration for q in quotes]
        return {
            'total_quotes': len(quotes),
            'avg_duration': sum(durations) / len(durations),
            'min_duration': min(durations),
            'max_duration': max(durations),
            'unique_speakers': len(set(q.speaker_name for q in quotes)),
            'unique_topics': len(set(q.topic for q in quotes)),
            'unique_episodes': len(set(q.get_episode_id() for q in quotes)),
            'sentiments': {sentiment: len([q for q in quotes if q.sentiment == sentiment]) 
                         for sentiment in set(q.sentiment for q in quotes)}
        }


# # Example usage
# if __name__ == "__main__":
#     # Load quotes from CSV
#     csv_path = Path("/home/nam-bui/Dev/video_trimming/sample/Quote_results.csv")
#     processor = QuoteProcessor()
    
#     # Load all quotes
#     quotes = processor.load_from_csv(csv_path)
#     print(f"Loaded {len(quotes)} quotes")
    
#     # Get statistics
#     stats = processor.get_statistics(quotes)
#     print("Statistics:", stats)
    
#     # Filter examples
#     business_quotes = processor.filter_by_topic(quotes, "Business")
#     garry_quotes = processor.filter_by_speaker(quotes, "Garry Tan")
#     short_quotes = processor.filter_by_duration(quotes, max_duration=5.0)
    
#     # Get top quotes
#     top_quotes = processor.get_top_quotes(quotes, limit=5)
    

