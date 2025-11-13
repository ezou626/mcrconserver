import { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { Button } from '../components/ui/button';
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from '../components/ui/card';
import { useAuth } from '../contexts/AuthContext';
import { apiService, type ApiKey, type ApiKeysResponse } from '../lib/api';

const ROLES = {
  OWNER: 0,
  ADMIN: 1,
  USER: 2,
} as const;

export default function ApiKeys() {
  const { state: authState, logout } = useAuth();
  const navigate = useNavigate();
  const [apiKeys, setApiKeys] = useState<ApiKey[]>([]);
  const [pagination, setPagination] = useState({
    page: 1,
    limit: 10,
    total_count: 0,
    total_pages: 0,
    has_next: false,
    has_prev: false,
  });
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [isCreating, setIsCreating] = useState(false);
  const [revoking, setRevoking] = useState<string | null>(null);

  const user = authState.user;
  const isOwner = user?.role === ROLES.OWNER;
  const isAdmin = user?.role === ROLES.ADMIN;

  // Redirect to login if not authenticated
  useEffect(() => {
    if (!authState.isLoading && !authState.isAuthenticated) {
      navigate('/');
    }
  }, [authState.isAuthenticated, authState.isLoading, navigate]);

  const fetchApiKeys = useCallback(
    async (page: number = 1) => {
      if (!user || (!isAdmin && !isOwner)) return;

      setIsLoading(true);
      setError(null);

      try {
        let response: ApiKeysResponse;
        if (isOwner) {
          response = await apiService.listAllApiKeys(page, pagination.limit);
        } else {
          response = await apiService.listApiKeys(page, pagination.limit);
        }

        setApiKeys(response.api_keys);
        setPagination(response.pagination);
      } catch (err) {
        setError(
          err instanceof Error ? err.message : 'Failed to load API keys'
        );
      } finally {
        setIsLoading(false);
      }
    },
    [user, isAdmin, isOwner, pagination.limit]
  );

  useEffect(() => {
    fetchApiKeys(1);
  }, [fetchApiKeys]);

  const handleCreateApiKey = async () => {
    setIsCreating(true);
    setError(null);

    try {
      const response = await apiService.createApiKey();
      if (response.success) {
        // Refresh the list
        await fetchApiKeys(pagination.page);
        // Show the new API key to user (in production, you might want a modal)
        alert(`New API Key created: ${response.api_key}`);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to create API key');
    } finally {
      setIsCreating(false);
    }
  };

  const handleRevokeApiKey = async (apiKey: string) => {
    if (!confirm('Are you sure you want to revoke this API key?')) {
      return;
    }

    setRevoking(apiKey);
    setError(null);

    try {
      const response = await apiService.revokeApiKey(apiKey);
      if (response.success) {
        // Refresh the list
        await fetchApiKeys(pagination.page);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to revoke API key');
    } finally {
      setRevoking(null);
    }
  };

  const handlePageChange = async (newPage: number) => {
    await fetchApiKeys(newPage);
  };

  const handleLogout = async () => {
    await logout();
    navigate('/');
  };

  const copyToClipboard = async (text: string) => {
    try {
      await navigator.clipboard.writeText(text);
      alert('API key copied to clipboard');
    } catch (err) {
      console.error('Failed to copy to clipboard:', err);
    }
  };

  if (authState.isLoading) {
    return (
      <div className="container mx-auto p-4">
        <Card>
          <CardContent className="p-6">
            <div className="text-center">Loading...</div>
          </CardContent>
        </Card>
      </div>
    );
  }

  if (!authState.isAuthenticated) {
    return (
      <div className="container mx-auto p-4">
        <Card>
          <CardContent className="p-6">
            <p>Not authenticated. Redirecting to login...</p>
          </CardContent>
        </Card>
      </div>
    );
  }

  if (!user || (!isAdmin && !isOwner)) {
    return (
      <div className="container mx-auto p-4">
        <Card>
          <CardContent className="p-6">
            <div>
              <p>Access denied. Admin or Owner role required.</p>
              <p className="text-sm text-gray-600 mt-2">
                Current user: {user?.username || 'Unknown'},Role:{' '}
                {user?.role !== undefined ? user.role : 'Unknown'} (Need role 0
                or 1)
              </p>
              <div className="mt-4">
                <Button onClick={() => navigate('/console')}>
                  Go to Console
                </Button>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="container mx-auto p-4">
      <div className="space-y-6">
        {/* Navigation Header */}
        <Card>
          <CardHeader className="pb-3">
            <div className="flex items-center justify-between">
              <div>
                <CardTitle>API Keys Management</CardTitle>
                <div className="flex items-center gap-4 mt-2 text-sm text-gray-600">
                  <span>User: {authState.user?.username}</span>
                  <span>Role: {isOwner ? 'Owner' : 'Admin'}</span>
                </div>
              </div>
              <div className="flex gap-2">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => navigate('/console')}
                >
                  Console
                </Button>
                <Button variant="outline" size="sm" onClick={handleLogout}>
                  Logout
                </Button>
              </div>
            </div>
          </CardHeader>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between">
            <CardTitle>{isOwner ? 'All API Keys' : 'My API Keys'}</CardTitle>
            <Button
              onClick={handleCreateApiKey}
              disabled={isCreating || isLoading}
            >
              {isCreating ? 'Creating...' : 'Create API Key'}
            </Button>
          </CardHeader>
          <CardContent>
            {error && (
              <div className="mb-4 p-3 bg-red-100 border border-red-400 text-red-700 rounded">
                {error}
              </div>
            )}

            {isLoading ? (
              <div className="text-center py-4">Loading...</div>
            ) : (
              <div className="space-y-4">
                {apiKeys.length === 0 ? (
                  <div className="text-center py-8 text-gray-500">
                    No API keys found
                  </div>
                ) : (
                  <div className="space-y-2">
                    {apiKeys.map((apiKey) => (
                      <div
                        key={apiKey.api_key}
                        className="flex items-center justify-between p-4 border rounded-lg"
                      >
                        <div className="flex-1">
                          <div className="flex items-center space-x-4">
                            <code className="text-sm bg-gray-100 px-2 py-1 rounded">
                              {apiKey.api_key.substring(0, 20)}...
                            </code>
                            {isOwner && apiKey.username && (
                              <span className="text-sm text-gray-600">
                                User: {apiKey.username}
                              </span>
                            )}
                            <span className="text-sm text-gray-500">
                              Created:{'  '}
                              {new Date(apiKey.created_at).toLocaleDateString()}
                            </span>
                          </div>
                        </div>
                        <div className="flex items-center space-x-2">
                          <Button
                            variant="outline"
                            size="sm"
                            onClick={() => copyToClipboard(apiKey.api_key)}
                          >
                            Copy
                          </Button>
                          <Button
                            variant="destructive"
                            size="sm"
                            onClick={() => handleRevokeApiKey(apiKey.api_key)}
                            disabled={revoking === apiKey.api_key}
                          >
                            {revoking === apiKey.api_key
                              ? 'Revoking...'
                              : 'Revoke'}
                          </Button>
                        </div>
                      </div>
                    ))}
                  </div>
                )}

                {/* Pagination */}
                {pagination.total_pages > 1 && (
                  <div className="flex items-center justify-between mt-6">
                    <div className="text-sm text-gray-600">
                      Showing {(pagination.page - 1) * pagination.limit + 1} to{' '}
                      {Math.min(
                        pagination.page * pagination.limit,
                        pagination.total_count
                      )}{' '}
                      of {pagination.total_count} results
                    </div>
                    <div className="flex items-center space-x-2">
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => handlePageChange(pagination.page - 1)}
                        disabled={!pagination.has_prev || isLoading}
                      >
                        Previous
                      </Button>
                      <span className="text-sm">
                        Page {pagination.page} of {pagination.total_pages}
                      </span>
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => handlePageChange(pagination.page + 1)}
                        disabled={!pagination.has_next || isLoading}
                      >
                        Next
                      </Button>
                    </div>
                  </div>
                )}
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
