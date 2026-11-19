import { createBrowserRouter, Navigate } from 'react-router'

import { Layout } from './components/Layout'
import { RequireAuth } from './components/RequireAuth'
import { AccountPage } from './pages/AccountPage'
import { ActivatePage } from './pages/ActivatePage'
import { CartPage } from './pages/CartPage'
import { ForgotPasswordPage } from './pages/ForgotPasswordPage'
import { HomePage } from './pages/HomePage'
import { LoginPage } from './pages/LoginPage'
import { ModeratorPage } from './pages/ModeratorPage'
import { MovieDetailPage } from './pages/MovieDetailPage'
import { MoviesPage } from './pages/MoviesPage'
import { NotFoundPage } from './pages/NotFoundPage'
import { PaymentCancelPage, PaymentSuccessPage } from './pages/PaymentResultPage'
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
      { path: '/cart', element: <CartPage /> },
      { path: '/payment/success', element: <PaymentSuccessPage /> },
      { path: '/payment/cancel', element: <PaymentCancelPage /> },
      {
        path: '/account',
        element: (
          <RequireAuth>
            <AccountPage />
          </RequireAuth>
        ),
      },
      {
        path: '/moderator',
        element: (
          <RequireAuth>
            <ModeratorPage />
          </RequireAuth>
        ),
      },
      // Link from the payment confirmation email.
      { path: '/purchased', element: <Navigate to="/account?tab=purchased" replace /> },
      { path: '*', element: <NotFoundPage /> },
    ],
  },
])
