namespace SkillRadar.Api.Contracts;

public record RoleDto(int Id, string Name);

public record SkillDemandDto(int SkillId, string Skill, string Category, int JobCount);

public record JobDto(
    long Id,
    string Company,
    string Title,
    string? Location,
    bool Remote,
    string Source,
    string ApplyUrl,
    DateTimeOffset? PostedAt,
    IReadOnlyList<string> Skills);

public record JobListDto(int Total, int Page, int PageSize, IReadOnlyList<JobDto> Items);

public record StatsDto(
    int ActiveJobs,
    int TotalSkills,
    int Roles,
    DateTimeOffset? LastRunAt,
    string? LastRunStatus);

public record IngestTriggeredDto(string JobId);
