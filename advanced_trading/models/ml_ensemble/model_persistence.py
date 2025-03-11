"""
Model Persistence Module
-----------------------
This module provides functionality for saving and loading trained models,
with support for versioning, metadata tracking, and model registry.

The module includes:
1. ModelPersistence class for saving and loading individual models
2. ModelRegistry class for managing a collection of models
3. Convenience functions for quick model persistence operations
4. Support for model versioning and metadata tracking
5. Integration with the ML Ensemble framework
"""

import os
import json
import pickle
import datetime
import hashlib
import logging
from typing import Dict, List, Any, Optional, Union, Tuple
import pandas as pd
import numpy as np
from sklearn.base import BaseEstimator

# Configure logging
logger = logging.getLogger(__name__)

class ModelPersistence:
    """
    Class for saving and loading trained models with metadata.
    
    This class provides methods for:
    - Saving models to disk with metadata
    - Loading models from disk
    - Tracking model versions
    - Managing model metadata
    """
    
    def __init__(self, base_dir: str = None):
        """
        Initialize the ModelPersistence instance.
        
        Parameters
        ----------
        base_dir : str, optional
            Base directory for model storage. If None, uses './models'.
        """
        self.base_dir = base_dir or os.path.join(os.getcwd(), 'models')
        os.makedirs(self.base_dir, exist_ok=True)
        logger.info(f"Initialized ModelPersistence with base directory: {self.base_dir}")
    
    def save_model(
        self,
        model: BaseEstimator,
        model_name: str,
        metadata: Dict[str, Any] = None,
        version: str = None,
        overwrite: bool = False
    ) -> str:
        """
        Save a trained model to disk with metadata.
        
        Parameters
        ----------
        model : BaseEstimator
            The trained model to save
        model_name : str
            Name of the model
        metadata : Dict[str, Any], optional
            Additional metadata to store with the model
        version : str, optional
            Version string. If None, generates a timestamp-based version
        overwrite : bool, default=False
            Whether to overwrite an existing model with the same name and version
            
        Returns
        -------
        str
            Path to the saved model
        """
        # Create model directory if it doesn't exist
        model_dir = os.path.join(self.base_dir, model_name)
        os.makedirs(model_dir, exist_ok=True)
        
        # Generate version if not provided
        if version is None:
            version = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Create version directory
        version_dir = os.path.join(model_dir, version)
        if os.path.exists(version_dir) and not overwrite:
            raise FileExistsError(f"Model {model_name} version {version} already exists. Use overwrite=True to overwrite.")
        
        os.makedirs(version_dir, exist_ok=True)
        
        # Prepare metadata
        if metadata is None:
            metadata = {}
        
        # Add standard metadata
        metadata.update({
            'model_name': model_name,
            'version': version,
            'created_at': datetime.datetime.now().isoformat(),
            'model_type': type(model).__name__,
        })
        
        # Add model parameters to metadata
        try:
            metadata['model_params'] = model.get_params()
        except (AttributeError, TypeError):
            logger.warning(f"Could not get parameters for model {model_name}")
        
        # Generate model hash
        try:
            model_bytes = pickle.dumps(model)
            metadata['model_hash'] = hashlib.md5(model_bytes).hexdigest()
        except Exception as e:
            logger.warning(f"Could not generate hash for model {model_name}: {e}")
        
        # Save model
        model_path = os.path.join(version_dir, 'model.pkl')
        with open(model_path, 'wb') as f:
            pickle.dump(model, f)
        
        # Save metadata
        metadata_path = os.path.join(version_dir, 'metadata.json')
        with open(metadata_path, 'w') as f:
            json.dump(metadata, f, indent=2, default=str)
        
        logger.info(f"Saved model {model_name} version {version} to {version_dir}")
        return version_dir
    
    def load_model(
        self,
        model_name: str,
        version: str = 'latest',
        with_metadata: bool = False
    ) -> Union[BaseEstimator, Tuple[BaseEstimator, Dict[str, Any]]]:
        """
        Load a model from disk.
        
        Parameters
        ----------
        model_name : str
            Name of the model to load
        version : str, default='latest'
            Version to load. If 'latest', loads the most recent version
        with_metadata : bool, default=False
            Whether to return metadata along with the model
            
        Returns
        -------
        Union[BaseEstimator, Tuple[BaseEstimator, Dict[str, Any]]]
            The loaded model, or a tuple of (model, metadata) if with_metadata=True
        """
        model_dir = os.path.join(self.base_dir, model_name)
        
        if not os.path.exists(model_dir):
            raise FileNotFoundError(f"Model {model_name} not found")
        
        # Find the version to load
        if version == 'latest':
            versions = [d for d in os.listdir(model_dir) 
                       if os.path.isdir(os.path.join(model_dir, d))]
            if not versions:
                raise FileNotFoundError(f"No versions found for model {model_name}")
            
            # Sort versions by creation time
            versions.sort(key=lambda v: os.path.getmtime(os.path.join(model_dir, v)), reverse=True)
            version = versions[0]
        
        version_dir = os.path.join(model_dir, version)
        if not os.path.exists(version_dir):
            raise FileNotFoundError(f"Version {version} not found for model {model_name}")
        
        # Load model
        model_path = os.path.join(version_dir, 'model.pkl')
        with open(model_path, 'rb') as f:
            model = pickle.load(f)
        
        if with_metadata:
            # Load metadata
            metadata_path = os.path.join(version_dir, 'metadata.json')
            with open(metadata_path, 'r') as f:
                metadata = json.load(f)
            return model, metadata
        
        return model
    
    def get_model_versions(self, model_name: str) -> List[str]:
        """
        Get all versions of a model.
        
        Parameters
        ----------
        model_name : str
            Name of the model
            
        Returns
        -------
        List[str]
            List of version strings
        """
        model_dir = os.path.join(self.base_dir, model_name)
        
        if not os.path.exists(model_dir):
            raise FileNotFoundError(f"Model {model_name} not found")
        
        versions = [d for d in os.listdir(model_dir) 
                   if os.path.isdir(os.path.join(model_dir, d))]
        
        # Sort versions by creation time
        versions.sort(key=lambda v: os.path.getmtime(os.path.join(model_dir, v)))
        
        return versions
    
    def get_model_metadata(self, model_name: str, version: str = 'latest') -> Dict[str, Any]:
        """
        Get metadata for a model version.
        
        Parameters
        ----------
        model_name : str
            Name of the model
        version : str, default='latest'
            Version to get metadata for. If 'latest', gets the most recent version
            
        Returns
        -------
        Dict[str, Any]
            Model metadata
        """
        model_dir = os.path.join(self.base_dir, model_name)
        
        if not os.path.exists(model_dir):
            raise FileNotFoundError(f"Model {model_name} not found")
        
        # Find the version
        if version == 'latest':
            versions = [d for d in os.listdir(model_dir) 
                       if os.path.isdir(os.path.join(model_dir, d))]
            if not versions:
                raise FileNotFoundError(f"No versions found for model {model_name}")
            
            # Sort versions by creation time
            versions.sort(key=lambda v: os.path.getmtime(os.path.join(model_dir, v)), reverse=True)
            version = versions[0]
        
        version_dir = os.path.join(model_dir, version)
        if not os.path.exists(version_dir):
            raise FileNotFoundError(f"Version {version} not found for model {model_name}")
        
        # Load metadata
        metadata_path = os.path.join(version_dir, 'metadata.json')
        with open(metadata_path, 'r') as f:
            metadata = json.load(f)
        
        return metadata
    
    def delete_model(self, model_name: str, version: str = None) -> None:
        """
        Delete a model or a specific version of a model.
        
        Parameters
        ----------
        model_name : str
            Name of the model to delete
        version : str, optional
            Version to delete. If None, deletes all versions
        """
        import shutil
        
        model_dir = os.path.join(self.base_dir, model_name)
        
        if not os.path.exists(model_dir):
            raise FileNotFoundError(f"Model {model_name} not found")
        
        if version is None:
            # Delete all versions
            shutil.rmtree(model_dir)
            logger.info(f"Deleted model {model_name} (all versions)")
        else:
            # Delete specific version
            version_dir = os.path.join(model_dir, version)
            if not os.path.exists(version_dir):
                raise FileNotFoundError(f"Version {version} not found for model {model_name}")
            
            shutil.rmtree(version_dir)
            logger.info(f"Deleted model {model_name} version {version}")
            
            # Check if there are any versions left
            versions = [d for d in os.listdir(model_dir) 
                       if os.path.isdir(os.path.join(model_dir, d))]
            if not versions:
                # No versions left, delete the model directory
                os.rmdir(model_dir)


class ModelRegistry:
    """
    Class for managing a collection of models.
    
    This class provides methods for:
    - Registering models with metadata
    - Retrieving models by name, tags, or other criteria
    - Tracking model performance
    - Managing model lifecycle
    """
    
    def __init__(self, base_dir: str = None):
        """
        Initialize the ModelRegistry instance.
        
        Parameters
        ----------
        base_dir : str, optional
            Base directory for model storage. If None, uses './models'.
        """
        self.persistence = ModelPersistence(base_dir)
        self.registry_file = os.path.join(self.persistence.base_dir, 'registry.json')
        self._load_registry()
        logger.info(f"Initialized ModelRegistry with base directory: {self.persistence.base_dir}")
    
    def _load_registry(self) -> None:
        """Load the registry from disk or create a new one if it doesn't exist."""
        if os.path.exists(self.registry_file):
            with open(self.registry_file, 'r') as f:
                self.registry = json.load(f)
        else:
            self.registry = {
                'models': {},
                'last_updated': datetime.datetime.now().isoformat()
            }
            self._save_registry()
    
    def _save_registry(self) -> None:
        """Save the registry to disk."""
        self.registry['last_updated'] = datetime.datetime.now().isoformat()
        with open(self.registry_file, 'w') as f:
            json.dump(self.registry, f, indent=2, default=str)
    
    def register_model(
        self,
        model: BaseEstimator,
        model_name: str,
        metadata: Dict[str, Any] = None,
        version: str = None,
        tags: List[str] = None,
        overwrite: bool = False
    ) -> str:
        """
        Register a model in the registry.
        
        Parameters
        ----------
        model : BaseEstimator
            The trained model to register
        model_name : str
            Name of the model
        metadata : Dict[str, Any], optional
            Additional metadata to store with the model
        version : str, optional
            Version string. If None, generates a timestamp-based version
        tags : List[str], optional
            Tags to associate with the model
        overwrite : bool, default=False
            Whether to overwrite an existing model with the same name and version
            
        Returns
        -------
        str
            Version of the registered model
        """
        # Prepare metadata
        if metadata is None:
            metadata = {}
        
        if tags is not None:
            metadata['tags'] = tags
        
        # Save the model
        version_dir = self.persistence.save_model(
            model=model,
            model_name=model_name,
            metadata=metadata,
            version=version,
            overwrite=overwrite
        )
        
        # Get the version from the directory name
        version = os.path.basename(version_dir)
        
        # Update registry
        if model_name not in self.registry['models']:
            self.registry['models'][model_name] = {
                'versions': [],
                'tags': tags or [],
                'created_at': datetime.datetime.now().isoformat(),
                'updated_at': datetime.datetime.now().isoformat()
            }
        
        # Add version to registry
        version_info = {
            'version': version,
            'created_at': datetime.datetime.now().isoformat(),
            'tags': tags or []
        }
        
        # Add performance metrics if available
        if 'performance' in metadata:
            version_info['performance'] = metadata['performance']
        
        # Add or update version in registry
        versions = self.registry['models'][model_name]['versions']
        for i, v in enumerate(versions):
            if v['version'] == version:
                versions[i] = version_info
                break
        else:
            versions.append(version_info)
        
        # Update model tags
        if tags:
            self.registry['models'][model_name]['tags'] = list(set(
                self.registry['models'][model_name]['tags'] + tags
            ))
        
        # Update timestamp
        self.registry['models'][model_name]['updated_at'] = datetime.datetime.now().isoformat()
        
        # Save registry
        self._save_registry()
        
        logger.info(f"Registered model {model_name} version {version}")
        return version
    
    def get_model(
        self,
        model_name: str,
        version: str = 'latest',
        with_metadata: bool = False
    ) -> Union[BaseEstimator, Tuple[BaseEstimator, Dict[str, Any]]]:
        """
        Get a model from the registry.
        
        Parameters
        ----------
        model_name : str
            Name of the model to get
        version : str, default='latest'
            Version to get. If 'latest', gets the most recent version
        with_metadata : bool, default=False
            Whether to return metadata along with the model
            
        Returns
        -------
        Union[BaseEstimator, Tuple[BaseEstimator, Dict[str, Any]]]
            The model, or a tuple of (model, metadata) if with_metadata=True
        """
        return self.persistence.load_model(
            model_name=model_name,
            version=version,
            with_metadata=with_metadata
        )
    
    def list_models(self, tags: List[str] = None) -> pd.DataFrame:
        """
        List all models in the registry, optionally filtered by tags.
        
        Parameters
        ----------
        tags : List[str], optional
            Tags to filter by. If provided, only models with all these tags are returned
            
        Returns
        -------
        pd.DataFrame
            DataFrame containing model information
        """
        models = []
        
        for model_name, model_info in self.registry['models'].items():
            # Filter by tags if provided
            if tags and not all(tag in model_info['tags'] for tag in tags):
                continue
            
            # Get the latest version
            versions = model_info['versions']
            if not versions:
                continue
            
            latest_version = max(versions, key=lambda v: v['created_at'])
            
            # Add model to list
            model_data = {
                'model_name': model_name,
                'latest_version': latest_version['version'],
                'versions_count': len(versions),
                'tags': ', '.join(model_info['tags']),
                'created_at': model_info['created_at'],
                'updated_at': model_info['updated_at']
            }
            
            # Add performance metrics if available
            if 'performance' in latest_version:
                for metric, value in latest_version['performance'].items():
                    model_data[f'performance_{metric}'] = value
            
            models.append(model_data)
        
        return pd.DataFrame(models)
    
    def get_model_versions(self, model_name: str) -> pd.DataFrame:
        """
        Get all versions of a model.
        
        Parameters
        ----------
        model_name : str
            Name of the model
            
        Returns
        -------
        pd.DataFrame
            DataFrame containing version information
        """
        if model_name not in self.registry['models']:
            raise ValueError(f"Model {model_name} not found in registry")
        
        versions = self.registry['models'][model_name]['versions']
        if not versions:
            return pd.DataFrame()
        
        # Convert to DataFrame
        df = pd.DataFrame(versions)
        
        # Add performance metrics as separate columns
        if 'performance' in df.columns:
            for metric in df['performance'].iloc[0].keys():
                df[f'performance_{metric}'] = df['performance'].apply(
                    lambda p: p.get(metric, None) if isinstance(p, dict) else None
                )
            
            df = df.drop('performance', axis=1)
        
        return df
    
    def update_model_performance(
        self,
        model_name: str,
        version: str,
        performance: Dict[str, float]
    ) -> None:
        """
        Update performance metrics for a model version.
        
        Parameters
        ----------
        model_name : str
            Name of the model
        version : str
            Version to update
        performance : Dict[str, float]
            Performance metrics to update
        """
        if model_name not in self.registry['models']:
            raise ValueError(f"Model {model_name} not found in registry")
        
        # Find the version
        versions = self.registry['models'][model_name]['versions']
        for i, v in enumerate(versions):
            if v['version'] == version:
                # Update performance metrics
                if 'performance' not in v:
                    v['performance'] = {}
                
                v['performance'].update(performance)
                
                # Update registry
                self._save_registry()
                
                # Update metadata file
                metadata = self.persistence.get_model_metadata(model_name, version)
                if 'performance' not in metadata:
                    metadata['performance'] = {}
                
                metadata['performance'].update(performance)
                
                metadata_path = os.path.join(
                    self.persistence.base_dir,
                    model_name,
                    version,
                    'metadata.json'
                )
                
                with open(metadata_path, 'w') as f:
                    json.dump(metadata, f, indent=2, default=str)
                
                logger.info(f"Updated performance metrics for model {model_name} version {version}")
                return
        
        raise ValueError(f"Version {version} not found for model {model_name}")
    
    def delete_model(self, model_name: str, version: str = None) -> None:
        """
        Delete a model or a specific version of a model.
        
        Parameters
        ----------
        model_name : str
            Name of the model to delete
        version : str, optional
            Version to delete. If None, deletes all versions
        """
        if model_name not in self.registry['models']:
            raise ValueError(f"Model {model_name} not found in registry")
        
        if version is None:
            # Delete all versions
            self.persistence.delete_model(model_name)
            
            # Remove from registry
            del self.registry['models'][model_name]
        else:
            # Delete specific version
            self.persistence.delete_model(model_name, version)
            
            # Remove version from registry
            versions = self.registry['models'][model_name]['versions']
            self.registry['models'][model_name]['versions'] = [
                v for v in versions if v['version'] != version
            ]
            
            # If no versions left, remove model from registry
            if not self.registry['models'][model_name]['versions']:
                del self.registry['models'][model_name]
        
        # Save registry
        self._save_registry()
        
        logger.info(f"Deleted model {model_name}{f' version {version}' if version else ''} from registry")


# Convenience functions

def save_model(
    model: BaseEstimator,
    model_name: str,
    metadata: Dict[str, Any] = None,
    version: str = None,
    base_dir: str = None,
    overwrite: bool = False
) -> str:
    """
    Save a trained model to disk with metadata.
    
    Parameters
    ----------
    model : BaseEstimator
        The trained model to save
    model_name : str
        Name of the model
    metadata : Dict[str, Any], optional
        Additional metadata to store with the model
    version : str, optional
        Version string. If None, generates a timestamp-based version
    base_dir : str, optional
        Base directory for model storage. If None, uses './models'
    overwrite : bool, default=False
        Whether to overwrite an existing model with the same name and version
        
    Returns
    -------
    str
        Path to the saved model
    """
    persistence = ModelPersistence(base_dir)
    return persistence.save_model(
        model=model,
        model_name=model_name,
        metadata=metadata,
        version=version,
        overwrite=overwrite
    )


def load_model(
    model_name: str,
    version: str = 'latest',
    base_dir: str = None,
    with_metadata: bool = False
) -> Union[BaseEstimator, Tuple[BaseEstimator, Dict[str, Any]]]:
    """
    Load a model from disk.
    
    Parameters
    ----------
    model_name : str
        Name of the model to load
    version : str, default='latest'
        Version to load. If 'latest', loads the most recent version
    base_dir : str, optional
        Base directory for model storage. If None, uses './models'
    with_metadata : bool, default=False
        Whether to return metadata along with the model
        
    Returns
    -------
    Union[BaseEstimator, Tuple[BaseEstimator, Dict[str, Any]]]
        The loaded model, or a tuple of (model, metadata) if with_metadata=True
    """
    persistence = ModelPersistence(base_dir)
    return persistence.load_model(
        model_name=model_name,
        version=version,
        with_metadata=with_metadata
    )


def register_model(
    model: BaseEstimator,
    model_name: str,
    metadata: Dict[str, Any] = None,
    version: str = None,
    tags: List[str] = None,
    base_dir: str = None,
    overwrite: bool = False
) -> str:
    """
    Register a model in the registry.
    
    Parameters
    ----------
    model : BaseEstimator
        The trained model to register
    model_name : str
        Name of the model
    metadata : Dict[str, Any], optional
        Additional metadata to store with the model
    version : str, optional
        Version string. If None, generates a timestamp-based version
    tags : List[str], optional
        Tags to associate with the model
    base_dir : str, optional
        Base directory for model storage. If None, uses './models'
    overwrite : bool, default=False
        Whether to overwrite an existing model with the same name and version
        
    Returns
    -------
    str
        Version of the registered model
    """
    registry = ModelRegistry(base_dir)
    return registry.register_model(
        model=model,
        model_name=model_name,
        metadata=metadata,
        version=version,
        tags=tags,
        overwrite=overwrite
    )


def list_models(tags: List[str] = None, base_dir: str = None) -> pd.DataFrame:
    """
    List all models in the registry, optionally filtered by tags.
    
    Parameters
    ----------
    tags : List[str], optional
        Tags to filter by. If provided, only models with all these tags are returned
    base_dir : str, optional
        Base directory for model storage. If None, uses './models'
        
    Returns
    -------
    pd.DataFrame
        DataFrame containing model information
    """
    registry = ModelRegistry(base_dir)
    return registry.list_models(tags=tags)


def get_model_versions(model_name: str, base_dir: str = None) -> pd.DataFrame:
    """
    Get all versions of a model.
    
    Parameters
    ----------
    model_name : str
        Name of the model
    base_dir : str, optional
        Base directory for model storage. If None, uses './models'
        
    Returns
    -------
    pd.DataFrame
        DataFrame containing version information
    """
    registry = ModelRegistry(base_dir)
    return registry.get_model_versions(model_name=model_name) 