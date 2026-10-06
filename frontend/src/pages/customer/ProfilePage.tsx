import { PageContainer } from "../../components/common/PageContainer";
import { useAuthStore } from "../../store/authStore";

export function ProfilePage() {
  const user = useAuthStore((state) => state.user);
  return (
    <PageContainer className="max-w-2xl py-10">
      <h1 className="text-4xl font-black text-ink">Profile</h1>
      <div className="mt-6 rounded-2xl border border-ink/10 bg-white p-6">
        <p className="text-sm text-ink/60">Name</p>
        <p className="text-lg font-semibold text-ink">{user?.full_name}</p>
        <p className="mt-4 text-sm text-ink/60">Email</p>
        <p className="text-lg font-semibold text-ink">{user?.email}</p>
        <p className="mt-4 text-sm text-ink/60">Role</p>
        <p className="text-lg font-semibold text-ink">{user?.role}</p>
      </div>
    </PageContainer>
  );
}
