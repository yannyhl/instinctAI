# advanced_trading/utils/event_detection.py

import pandas as pd
import numpy as np
from typing import Dict, List, Any, Optional, Union, Tuple
import logging
import requests
import re
import json
from datetime import datetime, timedelta
import time
from concurrent.futures import ThreadPoolExecutor
from textblob import TextBlob
import nltk
from nltk.tokenize import word_tokenize
from nltk.corpus import stopwords

logger = logging.getLogger(__name__)

# Initialize NLTK resources
try:
    nltk.data.find('tokenizers/punkt')
except LookupError:
    nltk.download('punkt')
    
try:
    nltk.data.find('corpora/stopwords')
except LookupError:
    nltk.download('stopwords')

class MarketEventDetector:
    """
    Detect significant market events from news, social media, and market data.
    
    Features:
    - News sentiment analysis
    - Social media trend monitoring
    - Market anomaly detection
    - Event classification and impact scoring
    """
    
    def __init__(self, api_keys: Optional[Dict[str, str]] = None, 
               cache_dir: Optional[str] = None,
               sentiment_threshold: float = 0.6,
               volatility_threshold: float = 3.0):
        """
        Initialize the market event detector.
        
        Args:
            api_keys: Dictionary of API keys for data sources
            cache_dir: Directory to cache results
            sentiment_threshold: Threshold for sentiment significance
            volatility_threshold: Threshold for volatility significance
        """
        self.api_keys = api_keys or {}
        self.cache_dir = cache_dir
        self.sentiment_threshold = sentiment_threshold
        self.volatility_threshold = volatility_threshold
        
        # Store detected events
        self.events = []
        
        # For social media trends
        self.trending_terms = set()
        self.trending_history = {}
        
        logger.info("Market Event Detector initialized")
    
    def detect_events(self, market_data: Optional[pd.DataFrame] = None,
                    start_date: Optional[str] = None,
                    end_date: Optional[str] = None,
                    symbols: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        """
        Detect market events across multiple data sources.
        
        Args:
            market_data: Market price data (optional)
            start_date: Start date for detection
            end_date: End date for detection
            symbols: List of symbols to analyze
            
        Returns:
            List of detected events
        """
        # Set default dates if not provided
        if not end_date:
            end_date = datetime.now().strftime('%Y-%m-%d')
        if not start_date:
            start_date = (datetime.strptime(end_date, '%Y-%m-%d') - timedelta(days=30)).strftime('%Y-%m-%d')
        
        symbols = symbols or ['BTC', 'ETH']
        
        logger.info(f"Detecting events from {start_date} to {end_date} for {len(symbols)} symbols")
        
        # Reset events
        self.events = []
        
        # Detect events from different sources
        news_events = self.detect_news_events(start_date, end_date, symbols)
        social_events = self.detect_social_events(start_date, end_date, symbols)
        
        # Detect market anomalies if market data is provided
        market_events = []
        if market_data is not None:
            market_events = self.detect_market_anomalies(market_data)
        
        # Combine all events
        all_events = news_events + social_events + market_events
        
        # Sort by date
        all_events.sort(key=lambda x: x['date'])
        
        # Store events
        self.events = all_events
        
        logger.info(f"Detected {len(all_events)} events")
        return all_events
    
    def detect_news_events(self, start_date: str, end_date: str, 
                         symbols: List[str]) -> List[Dict[str, Any]]:
        """
        Detect events from news sources.
        
        Args:
            start_date: Start date
            end_date: End date
            symbols: List of symbols
            
        Returns:
            List of news events
        """
        events = []
        
        # Use different news APIs based on available keys
        if 'newsapi' in self.api_keys:
            news_api_events = self._fetch_from_newsapi(start_date, end_date, symbols)
            events.extend(news_api_events)
        
        # Add more news sources as needed
        # ...
        
        # If no API keys, use a simple approach with general crypto news
        if not events:
            # Sample crypto news sources
            sources = [
                "https://cointelegraph.com/rss",
                "https://coindesk.com/arc/outboundfeeds/rss/"
            ]
            
            # Fetch and parse RSS feeds
            for source in sources:
                try:
                    # This is a placeholder - in production, you'd use proper RSS parsing
                    # For demo purposes, we'll create some sample events
                    sample_events = [
                        {
                            'title': f"Major news for {symbol} from {source.split('/')[2]}",
                            'date': datetime.strptime(end_date, '%Y-%m-%d') - timedelta(days=i),
                            'description': f"This is a sample news event for {symbol}",
                            'source': source,
                            'url': f"{source}article{i}",
                            'sentiment': 0.7 if i % 2 == 0 else -0.5,
                            'symbols': [symbol],
                            'type': 'news'
                        }
                        for i, symbol in enumerate(symbols)
                    ]
                    events.extend(sample_events)
                except Exception as e:
                    logger.warning(f"Error fetching news from {source}: {e}")
        
        # Process and score events
        processed_events = []
        for event in events:
            # Calculate sentiment if not already present
            if 'sentiment' not in event:
                event['sentiment'] = self._calculate_sentiment(event.get('title', '') + ' ' + event.get('description', ''))
            
            # Calculate impact score
            impact_score = self._calculate_impact_score(event)
            event['impact_score'] = impact_score
            
            # Add only significant events
            if abs(event['sentiment']) >= self.sentiment_threshold:
                processed_events.append(event)
        
        return processed_events
    
    def _fetch_from_newsapi(self, start_date: str, end_date: str, 
                          symbols: List[str]) -> List[Dict[str, Any]]:
        """
        Fetch news from News API.
        
        Args:
            start_date: Start date
            end_date: End date
            symbols: List of symbols
            
        Returns:
            List of news events
        """
        events = []
        api_key = self.api_keys.get('newsapi')
        
        if not api_key:
            return events
        
        # Base URL for News API
        base_url = "https://newsapi.org/v2/everything"
        
        # Fetch news for each symbol
        for symbol in symbols:
            try:
                # Create query parameters
                params = {
                    'q': f"crypto {symbol}",
                    'from': start_date,
                    'to': end_date,
                    'sortBy': 'publishedAt',
                    'language': 'en',
                    'apiKey': api_key
                }
                
                # Make request
                response = requests.get(base_url, params=params)
                
                if response.status_code == 200:
                    data = response.json()
                    
                    # Process articles
                    for article in data.get('articles', []):
                        event = {
                            'title': article.get('title', ''),
                            'date': datetime.strptime(article.get('publishedAt', ''), "%Y-%m-%dT%H:%M:%SZ"),
                            'description': article.get('description', ''),
                            'source': article.get('source', {}).get('name', ''),
                            'url': article.get('url', ''),
                            'symbols': [symbol],
                            'type': 'news'
                        }
                        
                        # Calculate sentiment
                        sentiment = self._calculate_sentiment(event['title'] + ' ' + event['description'])
                        event['sentiment'] = sentiment
                        
                        events.append(event)
                else:
                    logger.warning(f"Error fetching news for {symbol}: {response.status_code}")
            
            except Exception as e:
                logger.error(f"Error processing news for {symbol}: {e}")
        
        return events
    
    def detect_social_events(self, start_date: str, end_date: str, 
                           symbols: List[str]) -> List[Dict[str, Any]]:
        """
        Detect events from social media.
        
        Args:
            start_date: Start date
            end_date: End date
            symbols: List of symbols
            
        Returns:
            List of social media events
        """
        events = []
        
        # Use different social media APIs based on available keys
        if 'twitter' in self.api_keys:
            twitter_events = self._fetch_from_twitter(start_date, end_date, symbols)
            events.extend(twitter_events)
        
        if 'reddit' in self.api_keys:
            reddit_events = self._fetch_from_reddit(start_date, end_date, symbols)
            events.extend(reddit_events)
        
        # If no API keys, create sample events
        if not events:
            # Create sample events for demonstration
            sample_events = []
            for i, symbol in enumerate(symbols):
                # Generate dates within the range
                days_range = (datetime.strptime(end_date, '%Y-%m-%d') - 
                             datetime.strptime(start_date, '%Y-%m-%d')).days
                
                for j in range(min(3, days_range)):
                    event_date = datetime.strptime(end_date, '%Y-%m-%d') - timedelta(days=j)
                    
                    event = {
                        'title': f"Social media trend for {symbol}",
                        'date': event_date,
                        'description': f"Increased social activity for {symbol} with sentiment {'positive' if i % 2 == 0 else 'negative'}",
                        'source': 'social_simulation',
                        'url': '',
                        'sentiment': 0.8 if i % 2 == 0 else -0.7,
                        'symbols': [symbol],
                        'type': 'social',
                        'mentions': 1000 + i * 500,
                        'trending_score': 85 + i * 5
                    }
                    
                    sample_events.append(event)
            
            events.extend(sample_events)
        
        # Process and score events
        processed_events = []
        for event in events:
            # Calculate impact score
            impact_score = self._calculate_impact_score(event)
            event['impact_score'] = impact_score
            
            # Add only significant events
            if abs(event.get('sentiment', 0)) >= self.sentiment_threshold:
                processed_events.append(event)
        
        return processed_events
    
    def _fetch_from_twitter(self, start_date: str, end_date: str, 
                          symbols: List[str]) -> List[Dict[str, Any]]:
        """
        Fetch data from Twitter API.
        Note: This is a placeholder - actual implementation would use the Twitter API.
        
        Args:
            start_date: Start date
            end_date: End date
            symbols: List of symbols
            
        Returns:
            List of social events from Twitter
        """
        # This is a placeholder - in a real implementation, you would use the Twitter API
        return []
    
    def _fetch_from_reddit(self, start_date: str, end_date: str, 
                         symbols: List[str]) -> List[Dict[str, Any]]:
        """
        Fetch data from Reddit API.
        Note: This is a placeholder - actual implementation would use the Reddit API.
        
        Args:
            start_date: Start date
            end_date: End date
            symbols: List of symbols
            
        Returns:
            List of social events from Reddit
        """
        # This is a placeholder - in a real implementation, you would use the Reddit API
        return []
    
    def detect_market_anomalies(self, market_data: pd.DataFrame) -> List[Dict[str, Any]]:
        """
        Detect anomalies in market data.
        
        Args:
            market_data: Market price data
            
        Returns:
            List of market anomaly events
        """
        events = []
        
        # Check if required columns exist
        required_cols = ['close', 'volume']
        if not all(col in market_data.columns for col in required_cols):
            logger.warning("Market data missing required columns for anomaly detection")
            return events
        
        # Calculate returns
        if 'returns' not in market_data.columns:
            market_data['returns'] = market_data['close'].pct_change()
        
        # Calculate volatility
        if 'volatility' not in market_data.columns:
            market_data['volatility'] = market_data['returns'].rolling(window=20).std()
        
        # Detect price anomalies (significant returns)
        significant_returns = market_data[abs(market_data['returns']) > 0.05].copy()
        
        for idx, row in significant_returns.iterrows():
            event = {
                'title': f"Significant price movement",
                'date': idx if isinstance(idx, datetime) else pd.to_datetime(idx),
                'description': f"Price {'increased' if row['returns'] > 0 else 'decreased'} by {abs(row['returns'])*100:.2f}%",
                'source': 'market_data',
                'type': 'price_anomaly',
                'return': row['returns'],
                'price': row['close'],
                'symbols': [market_data.name if hasattr(market_data, 'name') else 'Unknown']
            }
            
            # Add sentiment based on direction
            event['sentiment'] = 0.7 if row['returns'] > 0 else -0.7
            
            # Calculate impact score
            impact_score = self._calculate_impact_score(event)
            event['impact_score'] = impact_score
            
            events.append(event)
        
        # Detect volume anomalies
        market_data['volume_change'] = market_data['volume'].pct_change()
        significant_volume = market_data[abs(market_data['volume_change']) > 0.3].copy()
        
        for idx, row in significant_volume.iterrows():
            event = {
                'title': f"Significant volume change",
                'date': idx if isinstance(idx, datetime) else pd.to_datetime(idx),
                'description': f"Volume {'increased' if row['volume_change'] > 0 else 'decreased'} by {abs(row['volume_change'])*100:.2f}%",
                'source': 'market_data',
                'type': 'volume_anomaly',
                'volume_change': row['volume_change'],
                'volume': row['volume'],
                'symbols': [market_data.name if hasattr(market_data, 'name') else 'Unknown']
            }
            
            # Add sentiment based on direction
            event['sentiment'] = 0.5 if row['volume_change'] > 0 else -0.5
            
            # Calculate impact score
            impact_score = self._calculate_impact_score(event)
            event['impact_score'] = impact_score
            
            events.append(event)
        
        # Detect volatility anomalies
        significant_volatility = market_data[market_data['volatility'] > market_data['volatility'].mean() * self.volatility_threshold].copy()
        
        for idx, row in significant_volatility.iterrows():
            event = {
                'title': f"High volatility detected",
                'date': idx if isinstance(idx, datetime) else pd.to_datetime(idx),
                'description': f"Volatility spike detected with value {row['volatility']*100:.2f}%",
                'source': 'market_data',
                'type': 'volatility_anomaly',
                'volatility': row['volatility'],
                'symbols': [market_data.name if hasattr(market_data, 'name') else 'Unknown']
            }
            
            # Add sentiment (volatility is generally considered negative)
            event['sentiment'] = -0.6
            
            # Calculate impact score
            impact_score = self._calculate_impact_score(event)
            event['impact_score'] = impact_score
            
            events.append(event)
        
        return events
    
    def _calculate_sentiment(self, text: str) -> float:
        """
        Calculate sentiment score for text.
        
        Args:
            text: Text to analyze
            
        Returns:
            Sentiment score (-1.0 to 1.0)
        """
        if not text:
            return 0.0
        
        try:
            # Use TextBlob for sentiment analysis
            blob = TextBlob(text)
            sentiment = blob.sentiment.polarity
            
            return sentiment
        except Exception as e:
            logger.error(f"Error calculating sentiment: {e}")
            return 0.0
    
    def _calculate_impact_score(self, event: Dict[str, Any]) -> float:
        """
        Calculate impact score for an event.
        
        Args:
            event: Event data
            
        Returns:
            Impact score (0.0 to 10.0)
        """
        # Base score
        score = 5.0
        
        # Adjust by sentiment intensity
        sentiment = event.get('sentiment', 0)
        score += abs(sentiment) * 2
        
        # Adjust by source reliability
        source = event.get('source', '')
        reliability_bonus = 0
        
        if source == 'market_data':
            reliability_bonus = 2
        elif 'coindesk' in source.lower() or 'cointelegraph' in source.lower():
            reliability_bonus = 1
        
        score += reliability_bonus
        
        # Adjust by event type
        event_type = event.get('type', '')
        
        if event_type == 'price_anomaly':
            if abs(event.get('return', 0)) > 0.1:  # 10% price change
                score += 2
            
        elif event_type == 'volume_anomaly':
            if abs(event.get('volume_change', 0)) > 0.5:  # 50% volume change
                score += 1.5
            
        elif event_type == 'social':
            # Adjust by mention count
            mentions = event.get('mentions', 0)
            if mentions > 5000:
                score += 1
            
            # Adjust by trending score
            trending = event.get('trending_score', 0)
            if trending > 90:
                score += 1
        
        # Cap score between 0 and 10
        return max(0, min(10, score))
    
    def get_top_events(self, n: int = 5) -> List[Dict[str, Any]]:
        """
        Get top N events by impact score.
        
        Args:
            n: Number of events to return
            
        Returns:
            List of top events
        """
        if not self.events:
            return []
        
        # Sort by impact score
        sorted_events = sorted(self.events, key=lambda x: x.get('impact_score', 0), reverse=True)
        
        # Return top N
        return sorted_events[:n]
    
    def get_sentiment_timeline(self) -> pd.DataFrame:
        """
        Get sentiment timeline from detected events.
        
        Returns:
            DataFrame with sentiment over time
        """
        if not self.events:
            return pd.DataFrame()
        
        # Create data points
        dates = []
        sentiments = []
        impact_scores = []
        
        for event in self.events:
            dates.append(event.get('date'))
            sentiments.append(event.get('sentiment', 0))
            impact_scores.append(event.get('impact_score', 0))
        
        # Create DataFrame
        df = pd.DataFrame({
            'date': dates,
            'sentiment': sentiments,
            'impact_score': impact_scores
        })
        
        # Set date as index
        df.set_index('date', inplace=True)
        
        # Sort by date
        df.sort_index(inplace=True)
        
        # Calculate weighted sentiment
        df['weighted_sentiment'] = df['sentiment'] * df['impact_score'] / 10
        
        return df