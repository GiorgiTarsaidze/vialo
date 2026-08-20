/**
 * Accessible fullscreen hook for map containers.
 * Uses Fullscreen API with CSS fallback. Handles:
 * - Escape key handling
 * - Focus return to trigger button
 * - Body scroll lock
 * - Map bounds refit after resize
 */

import { useState, useCallback, useEffect, useRef } from 'react';

interface UseFullscreenOptions {
  /** Called after entering/exiting fullscreen so the map can refit bounds */
  onResize?: () => void;
}

export function useFullscreen(options?: UseFullscreenOptions) {
  const [isFullscreen, setIsFullscreen] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);
  const triggerRef = useRef<HTMLButtonElement>(null);
  const previousOverflowRef = useRef<string>('');
  const cssFallbackActiveRef = useRef(false);
  const onResizeRef = useRef(options?.onResize);
  onResizeRef.current = options?.onResize;

  const enterFullscreen = useCallback(async () => {
    const el = containerRef.current;
    if (!el) return;

    // Try native Fullscreen API
    if (el.requestFullscreen) {
      try {
        await el.requestFullscreen();
        setIsFullscreen(true);
        return;
      } catch {
        // Fall through to CSS fallback
      }
    }

    // CSS fallback
    setIsFullscreen(true);
    previousOverflowRef.current = document.body.style.overflow;
    cssFallbackActiveRef.current = true;
    document.body.style.overflow = 'hidden';
  }, []);

  const exitFullscreen = useCallback(async () => {
    if (document.fullscreenElement) {
      try {
        await document.exitFullscreen();
      } catch {
        // Fall through
      }
    }

    setIsFullscreen(false);
    if (cssFallbackActiveRef.current) {
      document.body.style.overflow = previousOverflowRef.current;
      cssFallbackActiveRef.current = false;
    }

    // Return focus to trigger button
    setTimeout(() => {
      triggerRef.current?.focus();
    }, 50);
  }, []);

  const toggleFullscreen = useCallback(() => {
    if (isFullscreen) {
      exitFullscreen();
    } else {
      enterFullscreen();
    }
  }, [isFullscreen, enterFullscreen, exitFullscreen]);

  // Listen for native fullscreen changes (e.g. Escape pressed)
  useEffect(() => {
    const handleChange = () => {
      const active = !!document.fullscreenElement;
      setIsFullscreen(active);
      if (!active) {
        if (cssFallbackActiveRef.current) {
          document.body.style.overflow = previousOverflowRef.current;
          cssFallbackActiveRef.current = false;
        }
        setTimeout(() => {
          triggerRef.current?.focus();
        }, 50);
      }
      onResizeRef.current?.();
    };

    document.addEventListener('fullscreenchange', handleChange);
    return () => document.removeEventListener('fullscreenchange', handleChange);
  }, []);

  // Never leave the page scroll-locked if the map unmounts while using CSS fallback.
  useEffect(() => () => {
    if (cssFallbackActiveRef.current) {
      document.body.style.overflow = previousOverflowRef.current;
      cssFallbackActiveRef.current = false;
    }
  }, []);

  // Escape key handler for CSS fallback mode
  useEffect(() => {
    if (!isFullscreen || document.fullscreenElement) return;

    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        e.preventDefault();
        exitFullscreen();
      }
    };

    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, [isFullscreen, exitFullscreen]);

  // Call onResize after fullscreen state settles.
  useEffect(() => {
    const timer = setTimeout(() => onResizeRef.current?.(), 100);
    return () => clearTimeout(timer);
  }, [isFullscreen]);

  return {
    isFullscreen,
    containerRef,
    triggerRef,
    toggleFullscreen,
    enterFullscreen,
    exitFullscreen,
  };
}
