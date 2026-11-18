"use client";

import { useState } from "react";
import styles from "./channel.module.css";

interface LinkYouTubeFormProps {
  channelName: string;
  initialValue?: string;
  onSubmit: (channelRef: string) => Promise<void>;
  onCancel?: () => void;
}

export function LinkYouTubeForm({ channelName, initialValue = "", onSubmit, onCancel }: LinkYouTubeFormProps) {
  const [value, setValue] = useState(initialValue);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!value.trim()) return;
    setPending(true);
    setError(null);
    try {
      await onSubmit(value.trim());
    } catch (err) {
      setError(err instanceof Error ? err.message : "Não foi possível vincular o canal.");
    } finally {
      setPending(false);
    }
  };

  return (
    <section className={`${styles.panel} ${styles.panelPad}`} aria-labelledby="link-yt-title">
      <form className={styles.linkForm} onSubmit={handleSubmit}>
        <div>
          <h2 id="link-yt-title" className={styles.sectionTitle} style={{ fontSize: 18 }}>
            Vincular {channelName} ao YouTube
          </h2>
          <p className={styles.sectionHint} style={{ margin: "6px 0 0", lineHeight: 1.5 }}>
            Cole o @handle ou a URL do canal. Os dados públicos (inscritos, thumbnails, views) são lidos na hora, sem
            precisar de OAuth nem de worker rodando.
          </p>
        </div>
        <label htmlFor="yt-channel-ref" className="sr-only">
          @handle ou URL do canal no YouTube
        </label>
        <div className={styles.linkRow}>
          <input
            id="yt-channel-ref"
            className={styles.input}
            placeholder="youtube.com/@seucanal"
            value={value}
            onChange={(e) => setValue(e.target.value)}
            autoComplete="off"
            spellCheck={false}
            required
          />
          <button type="submit" className={`${styles.btn} ${styles.btnPrimary}`} disabled={pending}>
            {pending ? "Buscando…" : "Vincular canal"}
          </button>
          {onCancel && (
            <button type="button" className={styles.btn} onClick={onCancel}>
              Cancelar
            </button>
          )}
        </div>
        {error && (
          <p className={styles.errorText} role="alert">
            {error}
          </p>
        )}
      </form>
    </section>
  );
}
