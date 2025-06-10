from dataclasses import dataclass
from typing import List, Dict, Any, Optional
import json
import csv
from pathlib import Path

@dataclass
class WordTimestamp:
    """Represents a single word with timing information"""
    absolute_start_time: str
    duration: str
    absolute_end_time: str
    word: str
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'WordTimestamp':
        """Create WordTimestamp from dictionary data"""
        if 'M' in data:
            m_data = data['M']
            return cls(
                absolute_start_time=m_data.get('absolute_start_time', {}).get('S', ''),
                duration=m_data.get('duration', {}).get('S', ''),
                absolute_end_time=m_data.get('absolute_end_time', {}).get('S', ''),
                word=m_data.get('word', {}).get('S', '')
            )
        return cls('', '', '', '')
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert WordTimestamp to dictionary format"""
        return {
            "M": {
                "absolute_start_time": {"S": self.absolute_start_time},
                "duration": {"S": self.duration},
                "absolute_end_time": {"S": self.absolute_end_time},
                "word": {"S": self.word}
            }
        }

@dataclass
class TimeStamps:
    """Represents start and end timestamps"""
    start: str
    end: str
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'TimeStamps':
        """Create TimeStamps from dictionary data"""
        return cls(
            start=data.get('start', {}).get('S', ''),
            end=data.get('end', {}).get('S', '')
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert TimeStamps to dictionary format"""
        return {
            "start": {"S": self.start},
            "end": {"S": self.end}
        }

@dataclass
class ChunkModel:
    """Model representing a podcast chunk with all associated metadata"""
    podcast_title: str
    episode_chunk_id: str  # episode_title#chunk_no
    chunk: str
    chunk_audio_url: str
    chunk_description: str
    chunk_length: str
    chunk_title: str
    chunk_uuid: str
    genre: str
    sentiment: List[str]
    speakers: List[str]
    time_stamps: TimeStamps
    topics: List[str]
    word_timestamps: List[WordTimestamp]
    
    @property
    def episode_title(self) -> str:
        """Extract episode title from episode_chunk_id"""
        return self.episode_chunk_id.split('#')[0] if '#' in self.episode_chunk_id else self.episode_chunk_id
    
    @property
    def chunk_number(self) -> str:
        """Extract chunk number from episode_chunk_id"""
        return self.episode_chunk_id.split('#')[1] if '#' in self.episode_chunk_id else '0'
    
    @property
    def duration_seconds(self) -> float:
        """Convert chunk_length to float seconds"""
        try:
            return float(self.chunk_length)
        except (ValueError, TypeError):
            return 0.0
    
    @classmethod
    def from_csv_row(cls, row: Dict[str, str]) -> 'ChunkModel':
        """Create ChunkModel from CSV row"""
        # Parse sentiment
        sentiment = []
        try:
            sentiment_data = json.loads(row.get('sentiment', '[]'))
            sentiment = [item.get('S', '') for item in sentiment_data if 'S' in item]
        except (json.JSONDecodeError, TypeError):
            sentiment = []
        
        # Parse speakers
        speakers = []
        try:
            speakers_data = json.loads(row.get('speakers', '[]'))
            speakers = [item.get('S', '') for item in speakers_data if 'S' in item]
        except (json.JSONDecodeError, TypeError):
            speakers = []
        
        # Parse topics
        topics = []
        try:
            topics_data = json.loads(row.get('topics', '[]'))
            topics = [item.get('S', '') for item in topics_data if 'S' in item]
        except (json.JSONDecodeError, TypeError):
            topics = []
        
        # Parse time_stamps
        time_stamps = TimeStamps('', '')
        try:
            time_stamps_data = json.loads(row.get('time_stamps', '{}'))
            time_stamps = TimeStamps.from_dict(time_stamps_data)
        except (json.JSONDecodeError, TypeError):
            pass
        
        # Parse word_timestamps
        word_timestamps = []
        try:
            word_timestamps_data = json.loads(row.get('word_timestamps', '[]'))
            word_timestamps = [WordTimestamp.from_dict(item) for item in word_timestamps_data]
        except (json.JSONDecodeError, TypeError):
            word_timestamps = []
        
        return cls(
            podcast_title=row.get('podcast_title', ''),
            episode_chunk_id=row.get('episode_title#chunk_no', ''),
            chunk=row.get('chunk', ''),
            chunk_audio_url=row.get('chunk_audio_url', ''),
            chunk_description=row.get('chunk_description', ''),
            chunk_length=row.get('chunk_length', ''),
            chunk_title=row.get('chunk_title', ''),
            chunk_uuid=row.get('chunk_uuid', ''),
            genre=row.get('genre', ''),
            sentiment=sentiment,
            speakers=speakers,
            time_stamps=time_stamps,
            topics=topics,
            word_timestamps=word_timestamps
        )
    
    def to_csv_row(self) -> Dict[str, str]:
        """Convert ChunkModel to CSV row format"""
        # Convert sentiment to JSON string
        sentiment_json = json.dumps([{"S": s} for s in self.sentiment])
        
        # Convert speakers to JSON string
        speakers_json = json.dumps([{"S": s} for s in self.speakers])
        
        # Convert topics to JSON string
        topics_json = json.dumps([{"S": t} for t in self.topics])
        
        # Convert time_stamps to JSON string
        time_stamps_json = json.dumps(self.time_stamps.to_dict())
        
        # Convert word_timestamps to JSON string
        word_timestamps_json = json.dumps([wt.to_dict() for wt in self.word_timestamps])
        
        return {
            'podcast_title': self.podcast_title,
            'episode_title#chunk_no': self.episode_chunk_id,
            'chunk': self.chunk,
            'chunk_audio_url': self.chunk_audio_url,
            'chunk_description': self.chunk_description,
            'chunk_length': self.chunk_length,
            'chunk_title': self.chunk_title,
            'chunk_uuid': self.chunk_uuid,
            'genre': self.genre,
            'sentiment': sentiment_json,
            'speakers': speakers_json,
            'time_stamps': time_stamps_json,
            'topics': topics_json,
            'word_timestamps': word_timestamps_json
        }
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert ChunkModel to dictionary"""
        return {
            'podcast_title': self.podcast_title,
            'episode_title': self.episode_title,
            'chunk_number': self.chunk_number,
            'chunk': self.chunk,
            'chunk_audio_url': self.chunk_audio_url,
            'chunk_description': self.chunk_description,
            'chunk_length': self.chunk_length,
            'chunk_title': self.chunk_title,
            'chunk_uuid': self.chunk_uuid,
            'genre': self.genre,
            'sentiment': self.sentiment,
            'speakers': self.speakers,
            'time_stamps': {
                'start': self.time_stamps.start,
                'end': self.time_stamps.end
            },
            'topics': self.topics,
            'word_count': len(self.word_timestamps),
            'duration_seconds': self.duration_seconds
        }
    
    @classmethod
    def load_from_csv(cls, csv_path: str) -> List['ChunkModel']:
        """Load chunks from CSV file"""
        chunks = []
        csv_file = Path(csv_path)
        
        if not csv_file.exists():
            raise FileNotFoundError(f"CSV file not found: {csv_path}")
        
        with open(csv_file, 'r', encoding='utf-8') as file:
            reader = csv.DictReader(file)
            for row in reader:
                try:
                    chunk = cls.from_csv_row(row)
                    chunks.append(chunk)
                except Exception as e:
                    print(f"Error parsing row: {e}")
                    continue
        
        return chunks
    
    @classmethod
    def save_to_csv(cls, chunks: List['ChunkModel'], csv_path: str) -> None:
        """Save chunks to CSV file"""
        if not chunks:
            return
        
        csv_file = Path(csv_path)
        csv_file.parent.mkdir(parents=True, exist_ok=True)
        
        fieldnames = [
            'podcast_title', 'episode_title#chunk_no', 'chunk', 'chunk_audio_url',
            'chunk_description', 'chunk_length', 'chunk_title', 'chunk_uuid',
            'genre', 'sentiment', 'speakers', 'time_stamps', 'topics', 'word_timestamps'
        ]
        
        with open(csv_file, 'w', newline='', encoding='utf-8') as file:
            writer = csv.DictWriter(file, fieldnames=fieldnames)
            writer.writeheader()
            
            for chunk in chunks:
                try:
                    writer.writerow(chunk.to_csv_row())
                except Exception as e:
                    print(f"Error writing chunk {chunk.chunk_uuid}: {e}")
    
    def get_word_count(self) -> int:
        """Get the number of words in this chunk"""
        return len(self.word_timestamps)
    
    def get_start_time_seconds(self) -> float:
        """Get start time as float seconds"""
        try:
            return float(self.time_stamps.start)
        except (ValueError, TypeError):
            return 0.0
    
    def get_end_time_seconds(self) -> float:
        """Get end time as float seconds"""
        try:
            return float(self.time_stamps.end)
        except (ValueError, TypeError):
            return 0.0
    
    def contains_keyword(self, keyword: str) -> bool:
        """Check if chunk contains a specific keyword (case-insensitive)"""
        keyword_lower = keyword.lower()
        return (
            keyword_lower in self.chunk.lower() or
            keyword_lower in self.chunk_title.lower() or
            keyword_lower in self.chunk_description.lower() or
            any(keyword_lower in topic.lower() for topic in self.topics)
        )
    
    def filter_by_sentiment(self, target_sentiment: str) -> bool:
        """Check if chunk has a specific sentiment"""
        return target_sentiment.lower() in [s.lower() for s in self.sentiment]
    
    def __str__(self) -> str:
        """String representation of ChunkModel"""
        return (f"ChunkModel(title='{self.chunk_title}', "
                f"episode='{self.episode_title}', "
                f"chunk_no={self.chunk_number}, "
                f"duration={self.duration_seconds}s)")
    
    def __repr__(self) -> str:
        """Detailed string representation"""
        return self.__str__()
