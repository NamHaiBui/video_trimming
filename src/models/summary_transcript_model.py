from dataclasses import dataclass
from typing import List, Dict, Any, Optional, Tuple
import json
from pathlib import Path
import sys
import os
from utils.logging_config import setup_custom_logger

logging = setup_custom_logger(__name__)

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

try:
    from utils.interval_merger import merge_intervals
except ImportError:
    # Fallback for when running tests
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))
    from utils.interval_merger import merge_intervals

@dataclass
class SummaryChunkTimestamp:
    """Represents a merged timestamp interval for summary chunks"""
    start_time: float
    end_time: float
    text: str
    word_count: int
    
    def duration(self) -> float:
        """Get duration of the chunk in seconds"""
        return self.end_time - self.start_time
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary format"""
        return {
            'start_time': self.start_time,
            'end_time': self.end_time,
            'text': self.text,
            'word_count': self.word_count,
            'duration': self.duration()
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'SummaryChunkTimestamp':
        """Create from dictionary data"""
        return cls(
            start_time=float(data.get('start_time', 0)),
            end_time=float(data.get('end_time', 0)),
            text=data.get('text', ''),
            word_count=int(data.get('word_count', 0))
        )

@dataclass
class SummaryTranscriptModel:
    """Model for handling summary transcripts with merged chunk timestamps"""
    episode_title: str
    podcast_title: str
    total_duration: float
    summary_text: str
    summary_chunk_timestamps: List[SummaryChunkTimestamp]
    merge_threshold: float = 1.0  # seconds - gap threshold for merging intervals
    
    @property
    def total_chunks(self) -> int:
        """Get total number of summary chunks"""
        return len(self.summary_chunk_timestamps)
    
    @property
    def total_words(self) -> int:
        """Get total word count across all chunks"""
        return sum(chunk.word_count for chunk in self.summary_chunk_timestamps)
    
    @property
    def average_chunk_duration(self) -> float:
        """Get average duration of chunks"""
        if not self.summary_chunk_timestamps:
            return 0.0
        total_duration = sum(chunk.duration() for chunk in self.summary_chunk_timestamps)
        return total_duration / len(self.summary_chunk_timestamps)
    
    def _convert_word_timestamps_to_intervals(self, word_timestamps: List[Dict[str, Any]]) -> List[List[float]]:
        """Convert word timestamps to interval format [start, end]"""
        intervals = []
        for word_data in word_timestamps:
            try:
                if 'M' in word_data:
                    m_data = word_data['M']
                    start_time = float(m_data.get('absolute_start_time', {}).get('S', '0'))
                    end_time = float(m_data.get('absolute_end_time', {}).get('S', '0'))
                    intervals.append([start_time, end_time])
            except (ValueError, KeyError, TypeError):
                continue
        return intervals
    
    def _extract_text_from_intervals(self, word_timestamps: List[Dict[str, Any]], 
                                   merged_intervals: List[List[float]]) -> List[str]:
        """Extract text content for each merged interval"""
        interval_texts = []
        
        for interval_start, interval_end in merged_intervals:
            words_in_interval = []
            for word_data in word_timestamps:
                try:
                    if 'M' in word_data:
                        m_data = word_data['M']
                        word_start = float(m_data.get('absolute_start_time', {}).get('S', '0'))
                        word_end = float(m_data.get('absolute_end_time', {}).get('S', '0'))
                        word_text = m_data.get('word', {}).get('S', '')
                        
                        # Check if word falls within the interval (with some tolerance)
                        if (word_start >= interval_start - 0.1 and 
                            word_end <= interval_end + 0.1):
                            words_in_interval.append(word_text)
                except (ValueError, KeyError, TypeError):
                    continue
            
            interval_texts.append(' '.join(words_in_interval))
        
        return interval_texts
    
    def merge_close_intervals(self, word_timestamps: List[Dict[str, Any]], 
                            merge_threshold: Optional[float] = None) -> List[SummaryChunkTimestamp]:
        """
        Merge close word intervals using the interval merger utility
        
        Args:
            word_timestamps: List of word timestamp data from chunk model
            merge_threshold: Gap threshold for merging (uses instance default if None)
            
        Returns:
            List of SummaryChunkTimestamp objects with merged intervals
        """
        if merge_threshold is None:
            merge_threshold = self.merge_threshold
        logging.info(f"Merging intervals with threshold: {len(word_timestamps)} seconds")
        # Convert word timestamps to intervals
        intervals = [(word['start_time'], word['end_time'])   for word in word_timestamps]
        
        if not intervals:
            return []
        
        # Expand intervals to include merge threshold for gap detection
        expanded_intervals = []
        for start, end in intervals:
            expanded_intervals.append([start, end + merge_threshold])
        
        # Merge overlapping/close intervals
        merged_expanded = merge_intervals(expanded_intervals)
        logging.info(f"Merged {len(merged_expanded)} intervals from {len(expanded_intervals)} original intervals")
        logging.info(f"Expanded intervals: {merged_expanded}")
        merged_intervals = []
        for start, end in merged_expanded:
            merged_intervals.append([start, end - merge_threshold])
        
        # Extract text for each merged interval
        interval_texts = self._extract_text_from_intervals(word_timestamps, merged_intervals)
        
        # Create SummaryChunkTimestamp objects
        summary_chunks = []
        for i, ((start, end), text) in enumerate(zip(merged_intervals, interval_texts)):
            word_count = len(text.split()) if text.strip() else 0
            summary_chunks.append(SummaryChunkTimestamp(
                start_time=start,
                end_time=end,
                text=text.strip(),
                word_count=word_count
            ))
        
        return summary_chunks
    
    
    @classmethod
    def from_multiple_summary_chunks(cls, chunk_models: List[SummaryChunkTimestamp], podcast_title: str, 
                           episode_title: str, summary_text: str = "",
                           merge_threshold: float = 1.0) -> 'SummaryTranscriptModel':
        """
        Create SummaryTranscriptModel from multiple ChunkModel instances
        
        Args:
            chunk_models: List of ChunkModel instances
            podcast_title: Podcast title
            episode_title: Episode title
            summary_text: Summary text for the entire episode
            merge_threshold: Gap threshold for merging intervals
        """
        if not chunk_models:
            return cls(
                episode_title=episode_title,
                podcast_title=podcast_title,
                total_duration=0.0,
                summary_text=summary_text,
                summary_chunk_timestamps=[],
                merge_threshold=merge_threshold
            )
        
        # Combine all word timestamps from all chunks
        all_word_timestamps = []
        total_duration = 0.0
        
        for chunk in chunk_models:
            all_word_timestamps.append(chunk.to_dict())
            total_duration = max(total_duration, chunk.duration())
        
        instance = cls(
            episode_title=episode_title,
            podcast_title=podcast_title,
            total_duration=total_duration,
            summary_text=summary_text,
            summary_chunk_timestamps=[],
            merge_threshold=merge_threshold
        )
        
        # Merge intervals across all chunks
        instance.summary_chunk_timestamps = instance.merge_close_intervals(
            all_word_timestamps, merge_threshold
        )
        logging.info(f"Created SummaryTranscriptModel with {len(instance.summary_chunk_timestamps)} merged chunks")
        return instance
    
    def get_chunks_in_time_range(self, start_time: float, end_time: float) -> List[SummaryChunkTimestamp]:
        """Get chunks that fall within a specific time range"""
        return [
            chunk for chunk in self.summary_chunk_timestamps
            if chunk.start_time >= start_time and chunk.end_time <= end_time
        ]
    
    def get_text_in_time_range(self, start_time: float, end_time: float) -> str:
        """Get combined text for chunks within a time range"""
        chunks = self.get_chunks_in_time_range(start_time, end_time)
        return ' '.join(chunk.text for chunk in chunks)
    
    def update_merge_threshold(self, new_threshold: float) -> None:
        """Update merge threshold and regenerate chunks if word data is available"""
        self.merge_threshold = new_threshold
        # Note: Would need to store original word data to regenerate
    
    def get_chunk_at_time(self, time: float) -> Optional[SummaryChunkTimestamp]:
        """Get the chunk that contains a specific timestamp"""
        for chunk in self.summary_chunk_timestamps:
            if chunk.start_time <= time <= chunk.end_time:
                return chunk
        return None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary format"""
        return {
            'episode_title': self.episode_title,
            'podcast_title': self.podcast_title,
            'total_duration': self.total_duration,
            'summary_text': self.summary_text,
            'merge_threshold': self.merge_threshold,
            'total_chunks': self.total_chunks,
            'total_words': self.total_words,
            'average_chunk_duration': self.average_chunk_duration,
            'summary_chunk_timestamps': [chunk.to_dict() for chunk in self.summary_chunk_timestamps]
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'SummaryTranscriptModel':
        """Create from dictionary data"""
        chunks = [
            SummaryChunkTimestamp.from_dict(chunk_data)
            for chunk_data in data.get('summary_timestamps', [])
        ]
        logging.info(f"Loaded {len(chunks)} summary chunks from data")
        return cls.from_multiple_summary_chunks(chunks,
            episode_title=data.get('episode_title', ''),
            podcast_title=data.get('podcast_title', '')
        )
    
    @classmethod
    def load_from_json(cls, json_str: str) -> 'SummaryTranscriptModel':
        """Load from JSON string"""
        data = json.loads(json_str)
        
        return cls.from_dict(data)
    
    def save_to_json(self, json_path: str) -> None:
        """Save to JSON file"""
        json_file = Path(json_path)
        json_file.parent.mkdir(parents=True, exist_ok=True)
        
        with open(json_file, 'w', encoding='utf-8') as file:
            json.dump(self.to_dict(), file, indent=2, ensure_ascii=False)
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get detailed statistics about the summary transcript"""
        if not self.summary_chunk_timestamps:
            return {
                'total_chunks': 0,
                'total_words': 0,
                'total_duration': self.total_duration,
                'average_chunk_duration': 0,
                'shortest_chunk': 0,
                'longest_chunk': 0,
                'coverage_percentage': 0
            }
        
        durations = [chunk.duration() for chunk in self.summary_chunk_timestamps]
        actual_content_duration = sum(durations)
        
        return {
            'total_chunks': self.total_chunks,
            'total_words': self.total_words,
            'total_duration': self.total_duration,
            'actual_content_duration': actual_content_duration,
            'coverage_percentage': (actual_content_duration / self.total_duration * 100) if self.total_duration > 0 else 0,
            'average_chunk_duration': self.average_chunk_duration,
            'shortest_chunk': min(durations),
            'longest_chunk': max(durations),
            'merge_threshold': self.merge_threshold
        }
    
    def __str__(self) -> str:
        """String representation"""
        return (f"SummaryTranscriptModel(episode='{self.episode_title}', "
                f"chunks={self.total_chunks}, duration={self.total_duration}s, "
                f"merge_threshold={self.merge_threshold}s)")
    
    def __repr__(self) -> str:
        """Detailed string representation"""
        return self.__str__()
