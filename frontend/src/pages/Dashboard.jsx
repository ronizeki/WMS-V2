import React from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Package, Warehouse, Truck, ShoppingCart, TrendingUp, AlertTriangle } from 'lucide-react';

const stats = [
  { name: 'Total Products', value: '0', icon: Package, color: 'bg-blue-500' },
  { name: 'Total Stock Units', value: '0', icon: Warehouse, color: 'bg-green-500' },
  { name: 'Pending Receipts', value: '0', icon: Truck, color: 'bg-yellow-500' },
  { name: 'Pending Orders', value: '0', icon: ShoppingCart, color: 'bg-purple-500' },
];

const Dashboard = () => {
  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-gray-900">Dashboard</h1>
      
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        {stats.map((stat) => (
          <Card key={stat.name}>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">{stat.name}</CardTitle>
              <div className={`p-2 rounded-md ${stat.color}`}>
                <stat.icon className="h-4 w-4 text-white" />
              </div>
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">{stat.value}</div>
            </CardContent>
          </Card>
        ))}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <Card>
          <CardHeader>
            <CardTitle>Low Stock Alerts</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-gray-500 text-center py-8">No low stock alerts</p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Recent Stock Movements</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-gray-500 text-center py-8">No recent movements</p>
          </CardContent>
        </Card>
      </div>
    </div>
  );
};

export default Dashboard;