// =============================================================================
// PH Agent Hub — SessionSearch
// =============================================================================
// Ant Design Input.Search; GET /chat/sessions/search?q=; results in Ant Design List.
// =============================================================================

import { useState } from "react";
import { Input, List, Typography, Empty, Spin } from "antd";
import { useNavigate } from "react-router-dom";
import { searchSessions, SessionData } from "../services/chat";

const { Text } = Typography;
const { Search } = Input;

interface SessionSearchProps {
  onClose?: () => void;
}

export function SessionSearch({ onClose }: SessionSearchProps) {
  const [results, setResults] = useState<SessionData[]>([]);
  const [searching, setSearching] = useState(false);
  const [searched, setSearched] = useState(false);
  const navigate = useNavigate();

  const handleSearch = async (value: string) => {
    if (!value.trim()) {
      setResults([]);
      setSearched(false);
      return;
    }
    setSearching(true);
    setSearched(true);
    try {
      const data = await searchSessions(value);
      setResults(data);
    } catch {
      setResults([]);
    }
    setSearching(false);
  };

  const handleSelect = (session: SessionData) => {
    navigate(`/chat/${session.id}`);
    onClose?.();
  };

  return (
    <div style={{ padding: 16 }}>
      <Search
        placeholder="Search sessions..."
        onSearch={handleSearch}
        allowClear
        style={{ marginBottom: 16 }}
      />
      {searching ? (
        <div style={{ textAlign: "center", padding: 32 }}>
          <Spin />
        </div>
      ) : searched && results.length === 0 ? (
        <Empty description="No sessions found" />
      ) : (
        <List
          dataSource={results}
          renderItem={(item) => (
            <List.Item
              onClick={() => handleSelect(item)}
              style={{ cursor: "pointer" }}
            >
              <List.Item.Meta
                title={item.title}
                description={
                  <Text type="secondary">
                    {item.is_temporary ? "Temporary" : "Permanent"} ·{" "}
                    {new Date(item.updated_at).toLocaleDateString()}
                  </Text>
                }
              />
            </List.Item>
          )}
        />
      )}
    </div>
  );
}

export default SessionSearch;
