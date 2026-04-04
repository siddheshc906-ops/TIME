// frontend/src/components/ErrorBoundary.jsx
import React from 'react';
import { AlertCircle, RefreshCw, Home, ArrowLeft } from 'lucide-react';

class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { 
      hasError: false,
      error: null,
      errorInfo: null
    };
  }

  static getDerivedStateFromError(error) {
    return { hasError: true, error };
  }

  componentDidCatch(error, errorInfo) {
    console.error('Error caught by boundary:', error, errorInfo);
    this.setState({ errorInfo });
  }

  handleRefresh = () => {
    window.location.reload();
  };

  handleGoBack = () => {
    window.history.back();
  };

  handleGoHome = () => {
    window.location.href = '/';
  };

  render() {
    if (this.state.hasError) {
      return (
        <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-slate-50 to-slate-100">
          <div className="text-center p-8 max-w-md">
            {/* Error Icon with Animation */}
            <div className="relative mb-8">
              <div className="w-24 h-24 bg-red-100 rounded-full flex items-center justify-center mx-auto animate-pulse">
                <AlertCircle className="text-red-600" size={48} />
              </div>
              <div className="absolute -top-2 -right-2 w-8 h-8 bg-amber-400 rounded-full flex items-center justify-center text-white font-bold animate-bounce">
                !
              </div>
            </div>

            {/* Error Title */}
            <h1 className="text-3xl font-bold text-slate-800 mb-3">
              Oops! Something Went Wrong
            </h1>
            
            {/* Error Message */}
            <p className="text-slate-600 mb-6">
              {this.state.error?.message || 'An unexpected error occurred'}
            </p>

            {/* Friendly Explanation */}
            <div className="bg-white/80 backdrop-blur rounded-xl p-4 mb-6 border border-slate-200">
              <p className="text-sm text-slate-600">
                <span className="font-semibold">Don't worry!</span> Our team has been notified. 
                You can try refreshing or going back to the homepage.
              </p>
            </div>

            {/* Action Buttons */}
            <div className="flex flex-col sm:flex-row gap-3 justify-center">
              <button
                onClick={this.handleRefresh}
                className="px-6 py-3 bg-violet-600 text-white rounded-xl hover:bg-violet-700 transition flex items-center justify-center gap-2 shadow-lg hover:shadow-xl"
              >
                <RefreshCw size={18} />
                Refresh Page
              </button>
              
              <button
                onClick={this.handleGoBack}
                className="px-6 py-3 bg-white text-slate-700 rounded-xl hover:bg-slate-50 transition flex items-center justify-center gap-2 border border-slate-200"
              >
                <ArrowLeft size={18} />
                Go Back
              </button>
              
              <button
                onClick={this.handleGoHome}
                className="px-6 py-3 bg-slate-800 text-white rounded-xl hover:bg-slate-900 transition flex items-center justify-center gap-2"
              >
                <Home size={18} />
                Home
              </button>
            </div>

            {/* Error Details (Development Only) */}
            {process.env.NODE_ENV === 'development' && this.state.errorInfo && (
              <details className="mt-8 text-left p-4 bg-slate-800 rounded-xl">
                <summary className="text-sm font-medium text-white cursor-pointer">
                  Error Details (Dev Only)
                </summary>
                <pre className="mt-2 text-xs text-slate-300 overflow-auto max-h-60">
                  {this.state.error?.toString()}
                  {'\n\n'}
                  {this.state.errorInfo.componentStack}
                </pre>
              </details>
            )}
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}

export default ErrorBoundary;