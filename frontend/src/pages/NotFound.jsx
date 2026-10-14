import React from 'react';
import { Link } from 'react-router-dom';
import { Home } from 'lucide-react';
import { Button } from '../components/ui/button';

const NotFound = () => {
  return (
    <div className="flex flex-col items-center justify-center py-24 text-center">
      <p className="text-7xl font-bold text-slate-200">404</p>
      <h2 className="mt-4 text-2xl font-semibold text-slate-900">Page not found</h2>
      <p className="mt-2 text-sm text-slate-500">
        The page you are looking for does not exist or you may not have access to it.
      </p>
      <Link to="/dashboard" className="mt-6">
        <Button>
          <Home className="mr-2 h-4 w-4" />
          Back to dashboard
        </Button>
      </Link>
    </div>
  );
};

export default NotFound;
