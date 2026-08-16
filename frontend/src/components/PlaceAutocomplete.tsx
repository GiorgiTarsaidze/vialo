import { useRef, useCallback, useState } from 'react';
import type { UseAutocompleteReturn } from '../hooks/use-autocomplete';

interface PlaceAutocompleteProps {
  autocomplete: UseAutocompleteReturn;
  label: string;
  placeholder?: string;
  required?: boolean;
  disabled?: boolean;
}

export default function PlaceAutocomplete({
  autocomplete,
  label,
  placeholder,
  required,
  disabled,
}: PlaceAutocompleteProps) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [listVisible, setListVisible] = useState(true);
  const {
    query,
    setQuery,
    predictions,
    state,
    selectedPlace,
    selectPlace,
    activeIndex,
    setActiveIndex,
    listboxId,
  } = autocomplete;

  const isOpen = listVisible && state === 'results' && predictions.length > 0;

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent<HTMLInputElement>) => {
      if (e.key === 'Escape') {
        e.preventDefault();
        // Close the list without clearing input
        setListVisible(false);
        setActiveIndex(-1);
        return;
      }

      if (!isOpen) return;

      switch (e.key) {
        case 'ArrowDown':
          e.preventDefault();
          setActiveIndex(Math.min(activeIndex + 1, predictions.length - 1));
          break;
        case 'ArrowUp':
          e.preventDefault();
          setActiveIndex(Math.max(activeIndex - 1, -1));
          break;
        case 'Enter':
          e.preventDefault();
          if (activeIndex >= 0 && predictions[activeIndex]) {
            selectPlace(predictions[activeIndex]);
            setListVisible(false);
          }
          break;
      }
    },
    [isOpen, activeIndex, predictions, selectPlace, setActiveIndex],
  );

  const handleSelect = useCallback(
    (index: number) => {
      const place = predictions[index];
      if (place) {
        selectPlace(place);
        setListVisible(false);
        inputRef.current?.focus();
      }
    },
    [predictions, selectPlace],
  );

  const handleBlur = useCallback(
    (e: React.FocusEvent<HTMLDivElement>) => {
      // Only close if focus leaves the entire autocomplete container
      if (!e.currentTarget.contains(e.relatedTarget as Node)) {
        setListVisible(false);
        setActiveIndex(-1);
      }
    },
    [setActiveIndex],
  );

  const handleFocus = useCallback(() => {
    setListVisible(true);
  }, []);

  const activeDescendantId = activeIndex >= 0 ? `${listboxId}-option-${activeIndex}` : undefined;

  return (
    <div className="place-autocomplete" onBlur={handleBlur}>
      <label className="autocomplete-label" htmlFor={listboxId + '-input'}>
        {label}
        {required && <span aria-hidden="true"> *</span>}
      </label>
      <div className="autocomplete-input-wrap">
        <input
          ref={inputRef}
          id={listboxId + '-input'}
          className={`autocomplete-input ${selectedPlace ? 'autocomplete-input--selected' : ''}`}
          type="text"
          role="combobox"
          aria-autocomplete="list"
          aria-expanded={isOpen}
          aria-controls={listboxId}
          aria-activedescendant={activeDescendantId}
          aria-required={required}
          aria-invalid={required && !selectedPlace && query.length > 0 ? true : undefined}
          value={query}
          onChange={(e) => {
            setQuery(e.target.value);
            setListVisible(true);
          }}
          onKeyDown={handleKeyDown}
          onFocus={handleFocus}
          placeholder={placeholder}
          disabled={disabled}
          autoComplete="off"
        />
        {selectedPlace && (
          <button
            className="autocomplete-clear"
            type="button"
            onClick={() => {
              autocomplete.clearSelection();
              setListVisible(true);
              inputRef.current?.focus();
            }}
            aria-label={`Clear ${label}`}
          >
            ×
          </button>
        )}
        {state === 'loading' && (
          <span className="autocomplete-spinner" aria-hidden="true" />
        )}
      </div>

      {isOpen && (
        <ul
          id={listboxId}
          role="listbox"
          className="autocomplete-listbox"
          aria-label={`${label} suggestions`}
        >
          {predictions.map((place, i) => (
            <li
              key={place.placeId}
              id={`${listboxId}-option-${i}`}
              role="option"
              aria-selected={i === activeIndex}
              className={`autocomplete-option ${i === activeIndex ? 'autocomplete-option--active' : ''}`}
              onMouseDown={(e) => e.preventDefault()}
              onClick={() => handleSelect(i)}
            >
              <span className="option-name">{place.displayName}</span>
              <span className="option-address">{place.formattedAddress}</span>
            </li>
          ))}
        </ul>
      )}

      {state === 'empty' && (
        <p className="autocomplete-status" role="status">No places found.</p>
      )}
      {state === 'error' && (
        <p className="autocomplete-status autocomplete-status--error" role="alert">
          Could not load suggestions.
        </p>
      )}

      {/* Live region for result count */}
      <div aria-live="polite" aria-atomic="true" className="sr-only">
        {state === 'results' && predictions.length > 0 && (
          `${predictions.length} suggestion${predictions.length !== 1 ? 's' : ''} available`
        )}
        {state === 'empty' && 'No places found'}
      </div>

      {/* Google attribution */}
      <span className="autocomplete-attribution">
        Powered by Google
      </span>

      <style>{styles}</style>
    </div>
  );
}

const styles = `
.place-autocomplete {
  position: relative;
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
}

.autocomplete-label {
  font-size: 13px;
  font-weight: 600;
  color: var(--color-ink-muted);
}

.autocomplete-input-wrap {
  position: relative;
}

.autocomplete-input {
  width: 100%;
  padding: var(--space-3) var(--space-4);
  padding-right: 40px;
  font-size: 15px;
  line-height: 23px;
  color: var(--color-ink);
  background: var(--color-surface-strong);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-input);
  transition: border-color var(--duration-fast) ease;
}

.autocomplete-input:focus-visible {
  border-color: var(--color-primary);
  outline: 2px solid var(--color-focus);
  outline-offset: 2px;
}

.autocomplete-input--selected {
  border-color: var(--color-success);
  background: var(--color-surface);
}

.autocomplete-clear {
  position: absolute;
  right: var(--space-2);
  top: 50%;
  transform: translateY(-50%);
  width: 28px;
  height: 28px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 18px;
  color: var(--color-ink-muted);
  border-radius: 50%;
  min-height: 44px;
  min-width: 44px;
}

.autocomplete-clear:hover {
  color: var(--color-ink);
  background: var(--color-border);
}

.autocomplete-spinner {
  position: absolute;
  right: var(--space-3);
  top: 50%;
  transform: translateY(-50%);
  width: 16px;
  height: 16px;
  border: 2px solid var(--color-border);
  border-top-color: var(--color-primary);
  border-radius: 50%;
  animation: spin 600ms linear infinite;
}

@keyframes spin {
  to { transform: translateY(-50%) rotate(360deg); }
}

@media (prefers-reduced-motion: reduce) {
  .autocomplete-spinner { animation: none; }
}

.autocomplete-listbox {
  position: absolute;
  z-index: 100;
  top: 100%;
  left: 0;
  right: 0;
  margin-top: var(--space-1);
  list-style: none;
  background: var(--color-surface-strong);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-input);
  box-shadow: var(--shadow-floating);
  max-height: 240px;
  overflow-y: auto;
}

.autocomplete-option {
  padding: var(--space-3) var(--space-4);
  cursor: pointer;
  display: flex;
  flex-direction: column;
  gap: 1px;
  min-height: 44px;
  justify-content: center;
}

.autocomplete-option:hover,
.autocomplete-option--active {
  background: var(--color-primary-soft);
}

.option-name {
  font-size: 15px;
  font-weight: 500;
  color: var(--color-ink);
}

.option-address {
  font-size: 12px;
  color: var(--color-ink-muted);
  overflow-wrap: anywhere;
}

.autocomplete-status {
  font-size: 12px;
  color: var(--color-ink-muted);
  padding: var(--space-2) 0;
}

.autocomplete-status--error {
  color: var(--color-danger);
}

.autocomplete-attribution {
  font-size: 11px;
  color: var(--color-ink-muted);
  margin-top: var(--space-1);
}
`;
