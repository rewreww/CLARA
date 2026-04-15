import React from 'react';
import ChatPanel from '../components/ChatPanel';
import '../App.css';

const Dashboard: React.FC = () => {
  return (
    <div className="dashboard">
      <div style={{ display: 'flex', flex: 1 }}>
        <ChatPanel />
      </div>
    </div>
  );
};

export default Dashboard;