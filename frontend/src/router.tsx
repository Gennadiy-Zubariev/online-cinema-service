import { createBrowserRouter } from 'react-router'

import { Layout } from './components/Layout'
import { ActivatePage } from './pages/ActivatePage'
import { ForgotPasswordPage } from './pages/ForgotPasswordPage'
import { HomePage } from './pages/HomePage'
import { LoginPage } from './pages/LoginPage'
import { MovieDetailPage } from './pages/MovieDetailPage'
import { MoviesPage } from './pages/MoviesPage'
import { NotFoundPage } from './pages/NotFoundPage'
import { RegisterPage } from './pages/RegisterPage'
import { ResetPasswordPage } from './pages/ResetPasswordPage'

// Paths used in backend emails and Stripe redirects (FRONTEND_URL + path):
// /activate, /reset-password, /purchased, /payment/success, /payment/cancel.
export const router = createBrowserRouter([
  {
    element: <Layout />,
    children: [
      { path: '/', element: <HomePage /> },
      { path: '/movies', element: <MoviesPage /> },
      { path: '/movies/:movieId', element: <MovieDetailPage /> },
      { path: '/login', element: <LoginPage /> },
      { path: '/register', element: <RegisterPage /> },
      { path: '/activate', element: <ActivatePage /> },
      { path: '/forgot-password', element: <ForgotPasswordPage /> },
      { path: '/reset-password', element: <ResetPasswordPage /> },
      { path: '*', element: <NotFoundPage /> },
    ],
  },
])
