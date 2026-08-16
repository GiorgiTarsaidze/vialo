import { useState, useRef, useCallback, useEffect } from 'react';
import type { PlaceRef } from '../lib/types';
import { fetchAutocomplete } from '../lib/api-client';

export type AutocompleteState = 'idle' | 'loading' | 'results' | 'empty' | 'error';

export interface UseAutocompleteReturn {
  query: string;
  setQuery: (v: string) => void;
  predictions: PlaceRef[];
  state: AutocompleteState;
  selectedPlace: PlaceRef | null;
  selectPlace: (place: PlaceRef) => void;
  clearSelection: () => void;
  activeIndex: number;
  setActiveIndex: (i: number) => void;
  listboxId: string;
}

const DEBOUNCE_MS = 300;
const MIN_QUERY_LENGTH = 3;

export function useAutocomplete(id: string): UseAutocompleteReturn {
  const [query, setQueryInternal] = useState('');
  const [predictions, setPredictions] = useState<PlaceRef[]>([]);
  const [state, setState] = useState<AutocompleteState>('idle');
  const [selectedPlace, setSelectedPlace] = useState<PlaceRef | null>(null);
  const [activeIndex, setActiveIndex] = useState(-1);
  const abortRef = useRef<AbortController | null>(null);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const listboxId = `${id}-listbox`;

  const setQuery = useCallback((value: string) => {
    setQueryInternal(value);
    // If user types after selecting, clear the selection
    if (selectedPlace && value !== selectedPlace.displayName) {
      setSelectedPlace(null);
    }
  }, [selectedPlace]);

  const selectPlace = useCallback((place: PlaceRef) => {
    setSelectedPlace(place);
    setQueryInternal(place.displayName);
    setPredictions([]);
    setState('idle');
    setActiveIndex(-1);
  }, []);

  const clearSelection = useCallback(() => {
    setSelectedPlace(null);
    setQueryInternal('');
    setPredictions([]);
    setState('idle');
    setActiveIndex(-1);
  }, []);

  useEffect(() => {
    // Skip fetch if place already selected or query too short
    if (selectedPlace) return;
    if (query.length < MIN_QUERY_LENGTH) {
      setPredictions([]);
      setState('idle');
      return;
    }

    if (timerRef.current) clearTimeout(timerRef.current);
    abortRef.current?.abort();

    timerRef.current = setTimeout(() => {
      const controller = new AbortController();
      abortRef.current = controller;
      setState('loading');

      fetchAutocomplete(query, controller.signal)
        .then((res) => {
          if (controller.signal.aborted) return;
          setPredictions(res.predictions);
          setState(res.predictions.length > 0 ? 'results' : 'empty');
          setActiveIndex(-1);
        })
        .catch((err) => {
          if (controller.signal.aborted) return;
          if (err instanceof Error && err.name === 'AbortError') return;
          setState('error');
          setPredictions([]);
        });
    }, DEBOUNCE_MS);

    return () => {
      if (timerRef.current) clearTimeout(timerRef.current);
    };
  }, [query, selectedPlace]);

  return {
    query,
    setQuery,
    predictions,
    state,
    selectedPlace,
    selectPlace,
    clearSelection,
    activeIndex,
    setActiveIndex,
    listboxId,
  };
}
