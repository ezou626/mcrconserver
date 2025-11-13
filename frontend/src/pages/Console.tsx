import { useState, useRef, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '@/contexts/AuthContext';
import { apiService } from '@/lib/api';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Separator } from '@/components/ui/separator';

interface CommandHistory {
  id: string;
  command: string;
  message?: string;
  error?: string;
  timestamp: Date;
  isLoading?: boolean;
}

export default function Console() {
  const { state: authState, logout } = useAuth();
  const navigate = useNavigate();
  const [command, setCommand] = useState('');
  const [history, setHistory] = useState<CommandHistory[]>([]);
  const [commandHistoryIndex, setCommandHistoryIndex] = useState(-1);
  const [isConnected, setIsConnected] = useState(true);
  const terminalRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  // Redirect if not authenticated
  useEffect(() => {
    if (!authState.isAuthenticated) {
      navigate('/');
    }
  }, [authState.isAuthenticated, navigate]);

  // Auto-scroll to bottom when new content is added
  useEffect(() => {
    if (terminalRef.current) {
      terminalRef.current.scrollTop = terminalRef.current.scrollHeight;
    }
  }, [history]);

  // Focus input when component mounts
  useEffect(() => {
    inputRef.current?.focus();
  }, []);

  const handleLogout = async () => {
    await logout();
    navigate('/');
  };

  const executeCommand = async (cmd: string) => {
    if (!cmd.trim()) return;

    const commandId = Date.now().toString();
    const newCommand: CommandHistory = {
      id: commandId,
      command: cmd.trim(),
      timestamp: new Date(),
      isLoading: true,
    };

    setHistory((prev) => [...prev, newCommand]);
    setCommand('');
    setCommandHistoryIndex(-1);

    try {
      const response = await apiService.executeCommand(cmd.trim());

      setHistory((prev) =>
        prev.map((item) =>
          item.id === commandId
            ? {
                ...item,
                message: response.message || 'Command executed successfully',
                error: response.error,
                isLoading: false,
              }
            : item
        )
      );

      setIsConnected(true);
    } catch (error) {
      setHistory((prev) =>
        prev.map((item) =>
          item.id === commandId
            ? {
                ...item,
                error:
                  error instanceof Error
                    ? error.message
                    : 'Failed to execute command',
                isLoading: false,
              }
            : item
        )
      );

      // Check if it's a connection error
      if (error instanceof Error && error.message.includes('fetch')) {
        setIsConnected(false);
      }
    }
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    executeCommand(command);
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    const commandsOnly = history.filter((h) => h.command);

    if (e.key === 'ArrowUp') {
      e.preventDefault();
      if (commandsOnly.length > 0) {
        const newIndex = Math.min(
          commandHistoryIndex + 1,
          commandsOnly.length - 1
        );
        setCommandHistoryIndex(newIndex);
        setCommand(commandsOnly[commandsOnly.length - 1 - newIndex].command);
      }
    } else if (e.key === 'ArrowDown') {
      e.preventDefault();
      if (commandHistoryIndex > 0) {
        const newIndex = commandHistoryIndex - 1;
        setCommandHistoryIndex(newIndex);
        setCommand(commandsOnly[commandsOnly.length - 1 - newIndex].command);
      } else if (commandHistoryIndex === 0) {
        setCommandHistoryIndex(-1);
        setCommand('');
      }
    }
  };

  const formatTimestamp = (timestamp: Date) => {
    return timestamp.toLocaleTimeString('en-US', {
      hour12: false,
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
    });
  };

  const clearHistory = () => {
    setHistory([]);
  };

  if (!authState.isAuthenticated) {
    return <div>Redirecting...</div>;
  }

  return (
    <div className="min-h-screen bg-gray-50 p-4">
      <div className="mx-auto max-w-6xl">
        {/* Header */}
        <div className="mb-6">
          <Card>
            <CardHeader className="pb-3">
              <div className="flex items-center justify-between">
                <div>
                  <CardTitle>Minecraft RCON Console</CardTitle>
                  <div className="flex items-center gap-4 mt-2 text-sm text-gray-600">
                    <span>User: {authState.user?.username}</span>
                    <Separator orientation="vertical" className="h-4" />
                    <div className="flex items-center gap-2">
                      <div
                        className={`w-2 h-2 rounded-full ${
                          isConnected ? 'bg-green-500' : 'bg-red-500'
                        }`}
                      />
                      <span>{isConnected ? 'Connected' : 'Disconnected'}</span>
                    </div>
                  </div>
                </div>
                <div className="flex gap-2">
                  {(authState.user?.role === 0 ||
                    authState.user?.role === 1) && (
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => navigate('/keys')}
                    >
                      API Keys
                    </Button>
                  )}
                  <Button variant="outline" size="sm" onClick={clearHistory}>
                    Clear History
                  </Button>
                  <Button variant="outline" size="sm" onClick={handleLogout}>
                    Logout
                  </Button>
                </div>
              </div>
            </CardHeader>
          </Card>
        </div>

        {/* Terminal */}
        <div className="grid grid-cols-1 gap-6">
          <Card className="h-[600px] flex flex-col">
            <CardHeader className="pb-3">
              <CardTitle className="text-lg">Terminal Output</CardTitle>
            </CardHeader>
            <CardContent className="flex-1 flex flex-col p-0">
              {/* Terminal Display */}
              <div
                ref={terminalRef}
                className="flex-1 overflow-y-auto p-4 bg-black text-green-400 font-mono text-sm space-y-2"
              >
                {history.length === 0 && (
                  <div className="text-gray-500">
                    Welcome to the Minecraft RCON Console. Type commands below
                    to execute them on the server.
                    <br />
                    Examples: "list", "weather clear", "time set day"
                  </div>
                )}

                {history.map((entry) => (
                  <div key={entry.id} className="space-y-1">
                    <div className="flex items-center gap-2">
                      <span className="text-blue-400">
                        [{formatTimestamp(entry.timestamp)}]
                      </span>
                      <span className="text-yellow-400">$</span>
                      <span className="text-white">{entry.command}</span>
                    </div>

                    {entry.isLoading && (
                      <div className="text-yellow-400 ml-2">
                        Executing command...
                      </div>
                    )}

                    {entry.message && (
                      <div className="text-green-400 ml-2 whitespace-pre-wrap">
                        {entry.message}
                      </div>
                    )}

                    {entry.error && (
                      <div className="text-red-400 ml-2">
                        Error: {entry.error}
                      </div>
                    )}
                  </div>
                ))}
              </div>

              {/* Command Input */}
              <div className="border-t bg-gray-50 p-4">
                <form onSubmit={handleSubmit} className="flex gap-2">
                  <div className="flex-1 flex items-center gap-2 bg-black px-3 py-2 rounded border">
                    <span className="text-yellow-400 font-mono">$</span>
                    <Input
                      ref={inputRef}
                      type="text"
                      value={command}
                      onChange={(e) => setCommand(e.target.value)}
                      onKeyDown={handleKeyDown}
                      placeholder="Enter command..."
                      className="border-0 bg-transparent text-white font-mono focus-visible:ring-0 focus-visible:ring-offset-0"
                      disabled={!isConnected}
                    />
                  </div>
                  <Button
                    type="submit"
                    disabled={!command.trim() || !isConnected}
                  >
                    Execute
                  </Button>
                </form>
                {!isConnected && (
                  <div className="mt-2 text-sm text-red-600">
                    Connection lost. Please check the server status.
                  </div>
                )}
              </div>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}
