import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { Link } from 'react-router'

import { removeRating, removeReaction, setRating, setReaction } from '../api/movies'
import type { MovieDetail } from '../api/types'
import { useAuth } from '../auth/useAuth'
import { getErrorMessage } from '../utils/errors'
import { StarIcon, ThumbDownIcon, ThumbUpIcon } from './icons'
import styles from './MovieVotes.module.css'

const SCORES = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]

// Likes / dislikes and the 1-10 rating. The API returns only totals, so the
// user's own choice is not highlighted (decision of block 7).
export function MovieVotes({ movie }: { movie: MovieDetail }) {
  const { status } = useAuth()
  const queryClient = useQueryClient()
  const [hovered, setHovered] = useState(0)
  const [message, setMessage] = useState('')

  const vote = useMutation({
    mutationFn: (action: () => Promise<void>) => action(),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ['movie', movie.id] })
    },
  })

  function run(action: () => Promise<void>, doneText: string) {
    setMessage('')
    vote.mutate(action, { onSuccess: () => setMessage(doneText) })
  }

  const canVote = status === 'user'

  return (
    <section className={styles.votes}>
      <div className={styles.block}>
        <h2 className={styles.heading}>Реакції</h2>
        <div className={styles.row}>
          <button
            type="button"
            className="btn btn-secondary"
            disabled={!canVote || vote.isPending}
            onClick={() => run(() => setReaction(movie.id, true), 'Лайк зараховано.')}
          >
            <ThumbUpIcon size={18} /> {movie.likes}
          </button>
          <button
            type="button"
            className="btn btn-secondary"
            disabled={!canVote || vote.isPending}
            onClick={() => run(() => setReaction(movie.id, false), 'Дизлайк зараховано.')}
          >
            <ThumbDownIcon size={18} /> {movie.dislikes}
          </button>
          {canVote && (
            <button
              type="button"
              className={styles.linkButton}
              disabled={vote.isPending}
              onClick={() => run(() => removeReaction(movie.id), 'Реакцію прибрано.')}
            >
              Прибрати мою реакцію
            </button>
          )}
        </div>
      </div>

      <div className={styles.block}>
        <h2 className={styles.heading}>
          Оцінка глядачів{' '}
          <span className={styles.average}>
            {movie.rating !== null ? `${movie.rating.toFixed(1)} / 10` : 'ще немає'}
          </span>
          <span className="muted"> · оцінок: {movie.ratings_count}</span>
        </h2>
        {canVote && (
          <div className={styles.row}>
            <div
              className={styles.stars}
              role="group"
              aria-label="Ваша оцінка від 1 до 10"
              onMouseLeave={() => setHovered(0)}
            >
              {SCORES.map((score) => (
                <button
                  key={score}
                  type="button"
                  className={score <= hovered ? styles.starOn : undefined}
                  aria-label={`Оцінити на ${score}`}
                  title={String(score)}
                  disabled={vote.isPending}
                  onMouseEnter={() => setHovered(score)}
                  onFocus={() => setHovered(score)}
                  onClick={() =>
                    run(() => setRating(movie.id, score), `Вашу оцінку ${score} збережено.`)
                  }
                >
                  <StarIcon size={22} />
                </button>
              ))}
            </div>
            <button
              type="button"
              className={styles.linkButton}
              disabled={vote.isPending}
              onClick={() => run(() => removeRating(movie.id), 'Оцінку прибрано.')}
            >
              Прибрати мою оцінку
            </button>
          </div>
        )}
      </div>

      {!canVote && (
        <p className="muted">
          <Link to="/login">Увійдіть</Link>, щоб ставити реакції й оцінки.
        </p>
      )}
      {message && <p className={styles.message}>{message}</p>}
      {vote.isError && <p className="notice notice-error">{getErrorMessage(vote.error)}</p>}
    </section>
  )
}
