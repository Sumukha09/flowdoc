import { useEffect, useRef, useState } from 'react';
import { addDocumentsToRun, getRunDetails, getRunState, resumeRun } from '../api';

export default function useRunDetail(id) {
  const [state, setState] = useState(null);
  const [details, setDetails] = useState(null);
  const [loading, setLoading] = useState(true);
  const [initialDocIds, setInitialDocIds] = useState(() => {
    const saved = sessionStorage.getItem(`run_${id}_initial_docs`);
    return saved ? JSON.parse(saved) : null;
  });
  const [isUploading, setIsUploading] = useState(false);
  const [uploadError, setUploadError] = useState(null);
  const fileInputRef = useRef(null);

  useEffect(() => {
    let mounted = true;

    async function load() {
      try {
        const [nextState, nextDetails] = await Promise.all([
          getRunState(id),
          getRunDetails(id).catch(() => null),
        ]);
        if (mounted) {
          setState(nextState);
          setDetails(nextDetails);
          setLoading(false);

          if (nextDetails && initialDocIds === null) {
            const ids = nextDetails.documents.map((doc) => doc.id);
            setInitialDocIds(ids);
            sessionStorage.setItem(`run_${id}_initial_docs`, JSON.stringify(ids));
          }
        }
      } catch (error) {
        console.error(error);
        if (mounted) setLoading(false);
      }
    }

    load();
    const interval = setInterval(load, 3000);
    return () => {
      mounted = false;
      clearInterval(interval);
    };
  }, [id, initialDocIds]);

  const handleUpload = async (event) => {
    const files = Array.from(event.target.files);
    if (!files.length) return;

    setIsUploading(true);
    setUploadError(null);
    try {
      const uploadResponse = await addDocumentsToRun(id, files);

      if (uploadResponse && uploadResponse.existing_documents) {
        setInitialDocIds(uploadResponse.existing_documents);
        sessionStorage.setItem(
          `run_${id}_initial_docs`,
          JSON.stringify(uploadResponse.existing_documents),
        );
      }

      const [nextState, nextDetails] = await Promise.all([
        getRunState(id),
        getRunDetails(id).catch(() => null),
      ]);
      setState(nextState);
      setDetails(nextDetails);

      if (fileInputRef.current) fileInputRef.current.value = '';
    } catch (error) {
      setUploadError(error.message);
    } finally {
      setIsUploading(false);
    }
  };

  const handleResume = async (event) => {
    event.preventDefault();
    try {
      await resumeRun(id);
    } catch (error) {
      console.error(error);
      alert(error.message || 'Failed to resume operation');
    }
  };

  return {
    state,
    details,
    loading,
    initialDocIds,
    isUploading,
    uploadError,
    fileInputRef,
    handleUpload,
    handleResume,
  };
}
