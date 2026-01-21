"""
Service de nettoyage automatique des fichiers temporaires.
Supprime les fichiers CSV et PDF après 10 minutes d'inactivité.
"""
import os
import time
import threading
from pathlib import Path


class CleanupService:
    def __init__(self, upload_folder, output_folder, timeout_seconds=600, check_interval=60):
        """
        Initialise le service de nettoyage.
        
        Args:
            upload_folder: Dossier contenant les fichiers CSV uploadés
            output_folder: Dossier contenant les PDFs générés
            timeout_seconds: Temps en secondes avant suppression (défaut: 600 = 10 minutes)
            check_interval: Intervalle de vérification en secondes (défaut: 60 = 1 minute)
        """
        self.upload_folder = Path(upload_folder)
        self.output_folder = Path(output_folder)
        self.timeout_seconds = timeout_seconds
        self.check_interval = check_interval
        self.running = False
        self.thread = None
        
    def _get_activity_file(self, filepath):
        """Retourne le chemin du fichier d'activité associé."""
        return Path(str(filepath) + '.activity')
    
    def _get_last_activity(self, filepath):
        """Récupère le timestamp de dernière activité d'un fichier."""
        activity_file = self._get_activity_file(filepath)
        if activity_file.exists():
            try:
                with open(activity_file, 'r') as f:
                    return float(f.read().strip())
            except (ValueError, IOError):
                return None
        return None
    
    def _update_activity(self, filepath):
        """Met à jour le timestamp d'activité d'un fichier."""
        activity_file = self._get_activity_file(filepath)
        try:
            with open(activity_file, 'w') as f:
                f.write(str(time.time()))
        except IOError:
            pass
    
    def _should_delete(self, filepath):
        """Vérifie si un fichier doit être supprimé."""
        if not filepath.exists():
            return True
        
        last_activity = self._get_last_activity(filepath)
        if last_activity is None:
            # Si pas de fichier d'activité, utiliser le timestamp de modification du fichier
            last_activity = filepath.stat().st_mtime
        
        now = time.time()
        elapsed = now - last_activity
        
        # LOG DE DEBUG pour comprendre la suppression prématurée
        if elapsed < self.timeout_seconds and elapsed > -60: # Si le fichier est encore "jeune"
             # On ne logue rien ici pour ne pas flooder, sauf si on suspecte une erreur
             pass
        elif elapsed >= self.timeout_seconds:
            print(f"DEBUG Cleanup: File {filepath.name} is {int(elapsed)}s old (timeout={self.timeout_seconds}s). Deleting.")
            
        return elapsed >= self.timeout_seconds
    
    def _delete_file(self, filepath):
        """Supprime un fichier et son fichier d'activité associé."""
        try:
            if filepath.exists():
                filepath.unlink()
            activity_file = self._get_activity_file(filepath)
            if activity_file.exists():
                activity_file.unlink()
            return True
        except Exception as e:
            print(f"Error deleting {filepath}: {e}")
            return False
    
    def _cleanup_folder(self, folder):
        """Nettoie un dossier en supprimant les fichiers expirés."""
        if not folder.exists():
            return
        
        deleted_count = 0
        for filepath in folder.iterdir():
            # Ignorer les fichiers d'activité et autres fichiers cachés
            if filepath.name.startswith('.') or filepath.suffix == '.activity':
                continue
            
            if self._should_delete(filepath):
                if self._delete_file(filepath):
                    deleted_count += 1
        
        # Nettoyer les fichiers d'activité orphelins
        for filepath in folder.iterdir():
            if filepath.suffix == '.activity':
                # Vérifier si le fichier associé existe
                original_file = Path(str(filepath)[:-10])  # Enlever '.activity'
                if not original_file.exists():
                    try:
                        filepath.unlink()
                    except Exception:
                        pass
        
        return deleted_count
    
    def cleanup(self):
        """Effectue un nettoyage des deux dossiers."""
        upload_deleted = self._cleanup_folder(self.upload_folder)
        output_deleted = self._cleanup_folder(self.output_folder)
        
        if upload_deleted or output_deleted:
            print(f"Cleanup: Deleted {upload_deleted} upload files and {output_deleted} output files")
    
    def _run_loop(self):
        """Boucle principale du service de nettoyage."""
        while self.running:
            try:
                self.cleanup()
            except Exception as e:
                print(f"Error in cleanup service: {e}")
            
            # Attendre avant la prochaine vérification
            time.sleep(self.check_interval)
    
    def start(self):
        """Démarre le service de nettoyage en arrière-plan."""
        if self.running:
            return
        
        self.running = True
        self.thread = threading.Thread(target=self._run_loop, daemon=True)
        self.thread.start()
        print("Cleanup service started")
    
    def stop(self):
        """Arrête le service de nettoyage."""
        self.running = False
        if self.thread:
            self.thread.join(timeout=5)
        print("Cleanup service stopped")
    
    def mark_activity(self, file_id, file_type='upload'):
        """
        Marque l'activité pour un fichier.
        
        Args:
            file_id: ID du fichier
            file_type: 'upload' pour CSV, 'output' pour PDF
        """
        if file_type == 'upload':
            folder = self.upload_folder
        else:
            folder = self.output_folder
        
        # Trouver le fichier correspondant
        for filepath in folder.iterdir():
            if filepath.name.startswith(file_id) and not filepath.suffix == '.activity':
                self._update_activity(filepath)
                return True
        
        return False
