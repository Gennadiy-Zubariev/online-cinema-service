import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState, type FormEvent } from 'react'
import { Link } from 'react-router'

import { addComment, likeComment, listComments } from '../api/movies'
import type { Comment } from '../api/types'
import { useAuth } from '../auth/useAuth'
import { getErrorMessage } from '../utils/errors'
import { formatDateTime } from '../utils/format'
import styles from './Comments.module.css'
import { HeartIcon } from './icons'
import { Pagination } from './Pagination'

const PAGE_SIZE = 10

function CommentForm({
  movieId,
  parentId = null,
  onDone,
}: {
  movieId: number
  parentId?: number | null
  onDone?: () => void
}) {
  const queryClient = useQueryClient()
  const [text, setText] = useState('')
  const mutation = useMutation({
    mutationFn: () => addComment(movieId, text, parentId),
    onSuccess: async () => {
      setText('')
      await queryClient.invalidateQueries({ queryKey: ['comments', movieId] })
      onDone?.()
    },
  })

  function handleSubmit(event: FormEvent) {
    event.preventDefault()
    mutation.mutate()
  }

  return (
    <form className={styles.form} onSubmit={handleSubmit}>
      <textarea
        className="input"
        rows={parentId ? 2 : 3}
        maxLength={2000}
        required
        placeholder={parentId ? 'Ваша відповідь' : 'Що ви думаєте про фільм?'}
        aria-label={parentId ? 'Текст відповіді' : 'Текст коментаря'}
        value={text}
        onChange={(event) => setText(event.target.value)}
      />
      {mutation.isError && <p className="notice notice-error">{getErrorMessage(mutation.error)}</p>}
      <div className={styles.formButtons}>
        <button
          type="submit"
          className="btn btn-small"
          disabled={mutation.isPending || !text.trim()}
        >
          {parentId ? 'Відповісти' : 'Опублікувати'}
        </button>
        {onDone && (
          <button type="button" className="btn btn-secondary btn-small" onClick={onDone}>
            Скасувати
          </button>
        )}
      </div>
    </form>
  )
}

function CommentItem({ comment, onReply }: { comment: Comment; onReply?: () => void }) {
  const { status } = useAuth()
  const queryClient = useQueryClient()
  // PUT is idempotent: a second click does not add a like, so the button is
  // disabled after the first one (the API does not say if I liked before).
  const [liked, setLiked] = useState(false)
  const like = useMutation({
    mutationFn: () => likeComment(comment.id),
    onSuccess: async () => {
      setLiked(true)
      await queryClient.invalidateQueries({ queryKey: ['comments', comment.movie_id] })
    },
  })

  return (
    <article className={styles.comment}>
      <header className={styles.meta}>
        <strong>{comment.author_name ?? `Користувач #${comment.user_id}`}</strong>
        <time dateTime={comment.created_at}>{formatDateTime(comment.created_at)}</time>
      </header>
      <p className={styles.text}>{comment.text}</p>
      <div className={styles.actions}>
        <button
          type="button"
          className={styles.action}
          disabled={status !== 'user' || liked || like.isPending}
          onClick={() => like.mutate()}
          aria-label="Подобається"
        >
          <HeartIcon size={16} /> {comment.likes}
        </button>
        {onReply && status === 'user' && (
          <button type="button" className={styles.action} onClick={onReply}>
            Відповісти
          </button>
        )}
      </div>
    </article>
  )
}

export function Comments({ movieId }: { movieId: number }) {
  const { status } = useAuth()
  const [page, setPage] = useState(1)
  const [replyTo, setReplyTo] = useState<number | null>(null)

  const query = useQuery({
    queryKey: ['comments', movieId, page],
    queryFn: () => listComments(movieId, page, PAGE_SIZE),
    placeholderData: keepPreviousData,
  })

  return (
    <section className={styles.section}>
      <h2>Коментарі {query.data ? <span className="muted">{query.data.total}</span> : null}</h2>
      {status === 'user' ? (
        <CommentForm movieId={movieId} />
      ) : (
        <p className="muted">
          <Link to="/login">Увійдіть</Link>, щоб коментувати.
        </p>
      )}
      {query.isError && <p className="notice notice-error">{getErrorMessage(query.error)}</p>}
      {query.data?.items.length === 0 && <p className="muted">Коментарів ще немає.</p>}
      <div className={styles.list}>
        {query.data?.items.map((comment) => (
          <div key={comment.id}>
            <CommentItem comment={comment} onReply={() => setReplyTo(comment.id)} />
            <div className={styles.replies}>
              {comment.replies.map((reply) => (
                <CommentItem key={reply.id} comment={reply} />
              ))}
              {replyTo === comment.id && (
                <CommentForm
                  movieId={movieId}
                  parentId={comment.id}
                  onDone={() => setReplyTo(null)}
                />
              )}
            </div>
          </div>
        ))}
      </div>
      {query.data && (
        <Pagination page={page} pageSize={PAGE_SIZE} total={query.data.total} onChange={setPage} />
      )}
    </section>
  )
}
