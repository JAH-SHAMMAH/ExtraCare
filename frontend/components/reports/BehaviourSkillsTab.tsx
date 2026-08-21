/**
 * Report Setup tab: Behaviour & Skills domain management.
 * Allows admins to create, edit, and delete assessment domains for psychomotor and affective skills.
 */

import { useState } from 'react';
import { useAssessmentDomains, useCreateDomain, useUpdateDomain, useDeleteDomain } from '@/hooks/useAssessmentDomains';
import { Loader2, Plus, Edit2, Trash2, Check, X } from 'lucide-react';

interface BehaviourSkillsTabProps {
  canWrite?: boolean;
  sectionId?: string;
}

export function BehaviourSkillsTab({ canWrite = false, sectionId }: BehaviourSkillsTabProps) {
  const [domainType, setDomainType] = useState<'psychomotor' | 'affective'>('psychomotor');
  const [showForm, setShowForm] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [formData, setFormData] = useState({ name: '', position: 0 });

  const { data: domains = [], isLoading } = useAssessmentDomains(sectionId, domainType);
  const createDomain = useCreateDomain();
  const updateDomain = useUpdateDomain();
  const deleteDomain = useDeleteDomain();

  const handleSubmit = async () => {
    if (!formData.name.trim()) return;

    if (editingId) {
      await updateDomain.mutateAsync({
        id: editingId,
        payload: { name: formData.name, position: formData.position },
      });
      setEditingId(null);
    } else {
      await createDomain.mutateAsync({
        section_id: sectionId || '',
        domain_type: domainType,
        name: formData.name,
        position: formData.position,
      });
    }

    setFormData({ name: '', position: 0 });
    setShowForm(false);
  };

  const handleEdit = (id: string, name: string, position: number) => {
    setEditingId(id);
    setFormData({ name, position });
    setShowForm(true);
  };

  const handleCancel = () => {
    setShowForm(false);
    setEditingId(null);
    setFormData({ name: '', position: 0 });
  };

  return (
    <div className="space-y-6">
      {/* Type selector */}
      <div className="flex gap-2">
        {(['psychomotor', 'affective'] as const).map((type) => (
          <button
            key={type}
            onClick={() => setDomainType(type)}
            className={`px-4 py-2 font-semibold rounded-lg transition ${
              domainType === type
                ? 'bg-brand-600 text-white'
                : 'bg-slate-100 text-slate-700 hover:bg-slate-200'
            }`}
          >
            {type === 'psychomotor' ? 'Psychomotor' : 'Affective'} Skills
          </button>
        ))}
      </div>

      {/* Form */}
      {showForm && canWrite && (
        <div className="bg-white rounded-xl border border-slate-200 p-4 space-y-3">
          <input
            type="text"
            placeholder="Domain name (e.g., Communication)"
            value={formData.name}
            onChange={(e) => setFormData((p) => ({ ...p, name: e.target.value }))}
            className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
          />
          <input
            type="number"
            placeholder="Position"
            value={formData.position}
            onChange={(e) => setFormData((p) => ({ ...p, position: parseInt(e.target.value) || 0 }))}
            className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
          />
          <div className="flex gap-2">
            <button
              onClick={handleSubmit}
              disabled={createDomain.isPending || updateDomain.isPending}
              className="flex items-center gap-2 px-4 py-2 bg-brand-600 text-white font-semibold rounded-lg hover:bg-brand-700 disabled:opacity-50"
            >
              {(createDomain.isPending || updateDomain.isPending) && <Loader2 size={16} className="animate-spin" />}
              {editingId ? 'Update' : 'Create'}
            </button>
            <button
              onClick={handleCancel}
              className="px-4 py-2 bg-slate-200 text-slate-700 font-semibold rounded-lg hover:bg-slate-300"
            >
              Cancel
            </button>
          </div>
        </div>
      )}

      {/* Add button */}
      {canWrite && !showForm && (
        <button
          onClick={() => setShowForm(true)}
          className="flex items-center gap-2 px-4 py-2 bg-slate-100 text-slate-700 font-semibold rounded-lg hover:bg-slate-200"
        >
          <Plus size={16} /> Add Domain
        </button>
      )}

      {/* Domains list */}
      {isLoading ? (
        <div className="flex items-center justify-center py-8">
          <Loader2 className="animate-spin mr-2" size={20} />
          <span className="text-slate-500">Loading domains...</span>
        </div>
      ) : domains.length === 0 ? (
        <div className="bg-white rounded-xl border border-dashed border-slate-200 p-8 text-center">
          <p className="text-sm text-slate-500">No {domainType} domains created yet.</p>
        </div>
      ) : (
        <div className="bg-white rounded-xl border border-slate-200 divide-y">
          {domains.map((domain) => (
            <div key={domain.id} className="flex items-center justify-between p-4 hover:bg-slate-50">
              <div>
                <div className="font-semibold text-slate-900">{domain.name}</div>
                <div className="text-xs text-slate-500">Position {domain.position}</div>
              </div>
              {canWrite && (
                <div className="flex gap-2">
                  <button
                    onClick={() => handleEdit(domain.id, domain.name, domain.position)}
                    className="p-2 text-slate-600 hover:bg-slate-100 rounded"
                    title="Edit"
                  >
                    <Edit2 size={16} />
                  </button>
                  <button
                    onClick={() => {
                      if (confirm(`Delete "${domain.name}"?`)) {
                        deleteDomain.mutateAsync(domain.id);
                      }
                    }}
                    disabled={deleteDomain.isPending}
                    className="p-2 text-red-600 hover:bg-red-50 rounded disabled:opacity-50"
                    title="Delete"
                  >
                    {deleteDomain.isPending ? <Loader2 size={16} className="animate-spin" /> : <Trash2 size={16} />}
                  </button>
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
