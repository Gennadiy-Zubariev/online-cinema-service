import { Link } from 'react-router'

export function NotFoundPage() {
  return (
    <div className="page narrow">
      <h1>Сторінку не знайдено</h1>
      <p className="muted">Посилання застаріло або містить помилку.</p>
      <Link to="/movies" className="btn">
        Перейти до фільмів
      </Link>
    </div>
  )
}
